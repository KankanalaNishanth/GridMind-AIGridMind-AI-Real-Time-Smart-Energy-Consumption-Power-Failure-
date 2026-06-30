from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from backend.app.core.config import get_settings
from ml.preprocess import FEATURE_COLUMNS, prepare_training_frame

try:
    from xgboost import XGBRegressor
except Exception:  # pragma: no cover - optional dependency can fail on some CPUs.
    XGBRegressor = None


def train_models(
    raw_dir: Path,
    processed_path: Path,
    model_dir: Path,
    train_deep_models: bool = False,
    max_training_rows: int = 20000,
) -> dict:
    model_dir.mkdir(parents=True, exist_ok=True)
    telemetry = prepare_training_frame(raw_dir, processed_path)
    training_data = telemetry.head(max_training_rows).copy() if max_training_rows else telemetry.copy()
    training_data["next_consumption_kwh"] = training_data["power_consumption_kwh"].shift(-1).fillna(
        telemetry["power_consumption_kwh"]
    )

    x = training_data[FEATURE_COLUMNS]
    y = training_data["next_consumption_kwh"]
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, shuffle=False)

    if XGBRegressor is not None:
        forecast_model = XGBRegressor(
            n_estimators=80,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.9,
            objective="reg:squarederror",
            n_jobs=2,
            random_state=42,
        )
    else:
        from sklearn.ensemble import RandomForestRegressor

        forecast_model = RandomForestRegressor(n_estimators=160, random_state=42)

    forecast_pipeline = Pipeline([("scaler", StandardScaler()), ("model", forecast_model)])
    forecast_pipeline.fit(x_train, y_train)
    forecast_predictions = forecast_pipeline.predict(x_test)

    anomaly_pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("model", IsolationForest(n_estimators=220, contamination=0.04, random_state=42)),
        ]
    )
    anomaly_pipeline.fit(x)

    joblib.dump(forecast_pipeline, model_dir / "demand_forecast.joblib")
    joblib.dump(anomaly_pipeline, model_dir / "anomaly_detector.joblib")
    (model_dir / "features.json").write_text(json.dumps(FEATURE_COLUMNS, indent=2), encoding="utf-8")

    metrics = {
        "processed_rows": int(len(telemetry)),
        "training_rows": int(len(training_data)),
        "forecast_model": "XGBoost" if XGBRegressor is not None else "RandomForest fallback",
        "demand_mae": float(mean_absolute_error(y_test, forecast_predictions)),
        "anomaly_model": "IsolationForest",
    }
    (model_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    if train_deep_models:
        _try_train_sequence_and_prophet(training_data, model_dir)
    return metrics


def _try_train_sequence_and_prophet(telemetry, model_dir: Path) -> None:
    try:
        from tensorflow import keras
    except Exception:
        return

    values = telemetry["power_consumption_kwh"].to_numpy(dtype=np.float32)
    if len(values) < 128:
        return
    window = 24
    x_seq = np.array([values[i : i + window] for i in range(len(values) - window)])
    y_seq = values[window:]
    scale = max(float(values.max()), 1.0)
    x_seq = (x_seq / scale).reshape((-1, window, 1))
    y_seq = y_seq / scale
    model = keras.Sequential(
        [
            keras.layers.Input(shape=(window, 1)),
            keras.layers.LSTM(24),
            keras.layers.Dense(1),
        ]
    )
    model.compile(optimizer="adam", loss="mae")
    model.fit(x_seq, y_seq, epochs=2, batch_size=64, verbose=0)
    model.save(model_dir / "lstm_demand.keras")

    try:
        from prophet import Prophet
    except Exception:
        return
    daily = telemetry[["timestamp", "power_consumption_kwh"]].rename(
        columns={"timestamp": "ds", "power_consumption_kwh": "y"}
    )
    prophet = Prophet()
    prophet.fit(daily)
    with (model_dir / "prophet_model.joblib").open("wb") as handle:
        joblib.dump(prophet, handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train GridMind AI models from Telangana energy CSVs.")
    parser.add_argument("--raw-dir", type=Path, default=get_settings().raw_data_dir)
    parser.add_argument("--processed-path", type=Path, default=get_settings().processed_data_path)
    parser.add_argument("--model-dir", type=Path, default=get_settings().model_dir)
    parser.add_argument("--max-training-rows", type=int, default=20000)
    parser.add_argument(
        "--train-deep-models",
        action="store_true",
        help="Also train optional TensorFlow LSTM and Prophet artifacts.",
    )
    args = parser.parse_args()
    metrics = train_models(
        args.raw_dir,
        args.processed_path,
        args.model_dir,
        args.train_deep_models,
        args.max_training_rows,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
