"""
Model evaluation.

Ports Phase 8 of the original notebook ("Evaluation Summary") into a
reusable function. Re-derives the same test split (fixed random_state=42,
identical to training) so metrics are reproducible without needing to
carry test sets around as separate artifacts.
"""
import logging
import os

import joblib
import numpy as np
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
    silhouette_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from app.core.config import get_settings
from app.services.ml_pipeline import CLF_FEATURES

logger = logging.getLogger(__name__)


def evaluate_all_models(df) -> dict:
    """
    Recompute the same evaluation metrics as the notebook's Phase 8 cell:
      1. Random Forest — accuracy, ROC-AUC (on the held-out test split)
      2. Isolation Forest — anomaly count/rate (on the full dataset)
      3. SARIMA — MAE, RMSE, MAPE (in-sample fit quality)
      4. KMeans — silhouette score, cluster count

    Requires all 4 models to already be trained and saved (run
    train_pipeline.py first). Raises FileNotFoundError otherwise.
    """
    settings = get_settings()
    models_dir = settings.models_path

    for fname in ["rf_disruption.pkl", "iso_forest.pkl", "scaler_iso.pkl", "sarima_model.pkl", "kmeans.pkl", "scaler_kmeans.pkl"]:
        if not (models_dir / fname).exists():
            raise FileNotFoundError(f"{fname} not found in {models_dir} — run train_pipeline.py first.")

    summary: dict = {}

    # --- 1. Random Forest ---------------------------------------------
    rf_model = joblib.load(models_dir / "rf_disruption.pkl")
    X_clf = df[CLF_FEATURES].fillna(0)
    y_clf = df["disruption"]
    _, X_te, _, y_te = train_test_split(X_clf, y_clf, test_size=0.2, random_state=42)

    y_pred_rf = rf_model.predict(X_te)
    y_prob_rf = rf_model.predict_proba(X_te)[:, 1]
    summary["random_forest"] = {
        "accuracy_pct": round(float((y_pred_rf == y_te).mean() * 100), 2),
        "roc_auc": round(float(roc_auc_score(y_te, y_prob_rf)), 4),
    }

    # --- 2. Isolation Forest -------------------------------------------
    iso_model = joblib.load(models_dir / "iso_forest.pkl")
    scaler_iso = joblib.load(models_dir / "scaler_iso.pkl")
    from app.services.ml_pipeline import ISO_FEATURES
    X_iso = df[ISO_FEATURES].fillna(0)
    X_iso_scaled = scaler_iso.transform(X_iso)
    is_anomaly = (iso_model.predict(X_iso_scaled) == -1).astype(int)
    summary["isolation_forest"] = {
        "anomalies_detected": int(is_anomaly.sum()),
        "anomaly_rate_pct": round(float(is_anomaly.mean() * 100), 2),
        "normal_points": int((is_anomaly == 0).sum()),
    }

    # --- 3. SARIMA -------------------------------------------------------
    sarima_res = joblib.load(models_dir / "sarima_model.pkl")
    monthly_ts = df.groupby("month_num")["Units"].sum().sort_index().reset_index(drop=True)
    in_sample = sarima_res.fittedvalues

    mae = mean_absolute_error(monthly_ts, in_sample)
    rmse = float(np.sqrt(mean_squared_error(monthly_ts, in_sample)))
    mape = float(np.mean(np.abs((monthly_ts - in_sample) / monthly_ts)) * 100)
    summary["sarima"] = {
        "mae_million_kwh": round(mae / 1e6, 3),
        "rmse_million_kwh": round(rmse / 1e6, 3),
        "mape_pct": round(mape, 2),
    }

    # --- 4. KMeans --------------------------------------------------------
    kmeans_model = joblib.load(models_dir / "kmeans.pkl")
    scaler_kmeans = joblib.load(models_dir / "scaler_kmeans.pkl")
    circle_agg = df.groupby("Circle").agg(
        avg_units=("Units", "mean"),
        total_units=("Units", "sum"),
        avg_connections=("TotServices", "mean"),
        avg_billing_ratio=("billing_ratio", "mean"),
        avg_load_factor=("load_factor", "mean"),
        disruption_rate=("disruption", "mean"),
    ).dropna()
    X_km = scaler_kmeans.transform(circle_agg)
    sil = silhouette_score(X_km, kmeans_model.labels_)
    summary["kmeans"] = {
        "silhouette_score": round(float(sil), 4),
        "n_clusters": int(kmeans_model.n_clusters),
    }

    summary["saved_models"] = sorted(os.listdir(models_dir))
    logger.info("Evaluation complete: %s", summary)
    return summary
