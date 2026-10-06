"""
Model training pipeline.

Ports Phases 4-8 of the original notebook (Isolation Forest, Random
Forest, SARIMA, Prophet, KMeans + evaluation) into functions that
train, evaluate, and persist each model to `settings.models_path`.

This module has no FastAPI/route dependencies — it can be run
standalone via `train_pipeline.py` or imported into tests.
"""
import logging

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.statespace.sarimax import SARIMAX

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ISO_FEATURES = ["Units", "Load", "billing_ratio", "avg_units_per_conn", "load_factor"]
CLF_FEATURES = ["TotServices", "avg_units_per_conn", "load_factor", "month_num", "Load", "billing_ratio"]


def train_isolation_forest(df: pd.DataFrame) -> dict:
    """Anomaly detection on individual readings. Saves iso_forest.pkl + scaler_iso.pkl."""
    settings = get_settings()
    logger.info("Training Isolation Forest...")

    X = df[ISO_FEATURES].fillna(0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        contamination=settings.ISO_FOREST_CONTAMINATION, random_state=42, n_estimators=100
    )
    pred = model.fit_predict(X_scaled)
    score = model.score_samples(X_scaled)
    is_anomaly = (pred == -1).astype(int)

    joblib.dump(model, settings.models_path / "iso_forest.pkl")
    joblib.dump(scaler, settings.models_path / "scaler_iso.pkl")

    result = {
        "anomalies_detected": int(is_anomaly.sum()),
        "anomaly_rate_pct": round(float(is_anomaly.mean() * 100), 2),
    }
    logger.info("Isolation Forest done: %s", result)
    return result


def train_random_forest(df: pd.DataFrame) -> dict:
    """Disruption classifier. Saves rf_disruption.pkl."""
    settings = get_settings()
    logger.info("Training Random Forest...")

    X = df[CLF_FEATURES].fillna(0)
    y = df["disruption"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")
    model.fit(X_tr, y_tr)

    y_pred = model.predict(X_te)
    y_prob = model.predict_proba(X_te)[:, 1]
    auc = roc_auc_score(y_te, y_prob)
    report = classification_report(y_te, y_pred, target_names=["Normal", "Disruption"], output_dict=True)

    joblib.dump(model, settings.models_path / "rf_disruption.pkl")

    result = {"roc_auc": round(float(auc), 4), "classification_report": report}
    logger.info("Random Forest done: ROC-AUC=%.4f", auc)
    return result


def train_sarima(df: pd.DataFrame) -> dict:
    """Aggregate monthly demand forecast. Saves sarima_model.pkl."""
    settings = get_settings()
    logger.info("Training SARIMA...")

    monthly_ts = df.groupby("month_num")["Units"].sum().sort_index()
    last_month_num = int(monthly_ts.index[-1])

    # statsmodels requires a supported (RangeIndex/DatetimeIndex) index to
    # forecast out-of-sample; month_num values aren't guaranteed contiguous
    # from 0, so we fit on a plain RangeIndex and map positions back to
    # real month numbers ourselves.
    ts = monthly_ts.reset_index(drop=True)
    sarima = SARIMAX(
        ts, order=(1, 1, 1), seasonal_order=(0, 0, 0, 0),
        enforce_stationarity=False, enforce_invertibility=False,
    )
    sarima_res = sarima.fit(disp=False)

    steps = settings.SARIMA_FORECAST_STEPS
    forecast = sarima_res.get_forecast(steps=steps)
    fc_mean = forecast.predicted_mean

    joblib.dump(sarima_res, settings.models_path / "sarima_model.pkl")
    # Persist the last training month_num so the API can map the model's
    # internal (0-based) forecast positions back to real month numbers.
    with open(settings.models_path / "sarima_last_month.txt", "w") as f:
        f.write(str(last_month_num))

    forecast_months = list(range(last_month_num + 1, last_month_num + steps + 1))
    result = {
        "forecast_steps": steps,
        "forecast": [
            {"month": int(m), "predicted_units": float(v)}
            for m, v in zip(forecast_months, fc_mean.values)
        ],
    }
    logger.info("SARIMA done: %d-step forecast generated", steps)
    return result


def train_prophet(df: pd.DataFrame) -> dict | None:
    """Optional secondary forecaster. Skipped gracefully if prophet isn't installed."""
    settings = get_settings()
    try:
        from prophet import Prophet
    except ImportError:
        logger.warning("prophet not installed — skipping Prophet forecast (pip install prophet)")
        return None

    logger.info("Training Prophet...")
    monthly_ts = df.groupby("month_num")["Units"].sum()
    df_prophet = monthly_ts.reset_index()
    df_prophet.columns = ["ds", "y"]
    df_prophet["ds"] = pd.date_range(start="2023-01-01", periods=len(df_prophet), freq="MS")

    m = Prophet(yearly_seasonality=False, weekly_seasonality=False,
                daily_seasonality=False, seasonality_mode="additive")
    m.fit(df_prophet)
    future = m.make_future_dataframe(periods=settings.SARIMA_FORECAST_STEPS, freq="MS")
    forecast = m.predict(future)

    joblib.dump(m, settings.models_path / "prophet_model.pkl")

    tail = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(settings.SARIMA_FORECAST_STEPS)
    result = {"forecast": tail.to_dict(orient="records")}
    logger.info("Prophet done")
    return result


def train_kmeans(df: pd.DataFrame) -> dict:
    """Circle-level clustering. Saves kmeans.pkl + scaler_kmeans.pkl + circle_clusters.csv."""
    settings = get_settings()
    logger.info("Training KMeans clustering...")

    circle_agg = df.groupby("Circle").agg(
        avg_units=("Units", "mean"),
        total_units=("Units", "sum"),
        avg_connections=("TotServices", "mean"),
        avg_billing_ratio=("billing_ratio", "mean"),
        avg_load_factor=("load_factor", "mean"),
        disruption_rate=("disruption", "mean"),
    ).dropna()

    scaler = StandardScaler()
    X = scaler.fit_transform(circle_agg)

    k = settings.KMEANS_N_CLUSTERS
    model = KMeans(n_clusters=k, random_state=42, n_init=10)
    circle_agg["cluster"] = model.fit_predict(X)

    joblib.dump(model, settings.models_path / "kmeans.pkl")
    joblib.dump(scaler, settings.models_path / "scaler_kmeans.pkl")
    circle_agg.to_csv(settings.models_path / "circle_clusters.csv")

    result = {
        "n_clusters": k,
        "clusters": circle_agg.reset_index().to_dict(orient="records"),
    }
    logger.info("KMeans done: %d circles clustered into %d groups", len(circle_agg), k)
    return result


def run_full_pipeline(df: pd.DataFrame) -> dict:
    """Train every model in sequence and return a combined summary dict."""
    summary = {
        "rows_processed": len(df),
        "circles": int(df["Circle"].nunique()),
        "isolation_forest": train_isolation_forest(df),
        "random_forest": train_random_forest(df),
        "sarima": train_sarima(df),
        "kmeans": train_kmeans(df),
    }
    prophet_result = train_prophet(df)
    if prophet_result:
        summary["prophet"] = prophet_result
    return summary
