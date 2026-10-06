# GridMind AI — Backend Service

FastAPI REST API powering the GridMind AI smart energy and power failure prediction system.

## Endpoints

- `GET  /api/v1/health` — System status, loaded models, database connection
- `POST /api/v1/predict/disruption` — Random Forest power disruption risk classification
- `POST /api/v1/predict/anomaly` — Isolation Forest smart meter anomaly scoring
- `GET  /api/v1/predict/forecast` — Multi-step SARIMA consumption forecasting
- `GET  /api/v1/dashboard/clusters` — K-Means circle cluster profiles
- `GET  /api/v1/dashboard/summary` — Aggregate telemetry and anomaly counts
- `GET  /api/v1/dashboard/image` — Serves generated matplotlib report PNG
- `POST /api/v1/stream/simulate` — Kafka producer/consumer telemetry streaming replay
- `GET  /api/v1/data/consumption` — Telemetry data records (MongoDB or CSV cache)
- `GET  /api/v1/data/alerts` — Power disruption alerts (MongoDB or CSV cache)
- `GET  /api/v1/evaluate/summary` — Model performance metrics JSON

## Run Backend

```bash
# Option 1: Double-click start_backend.bat

# Option 2: Python
python run_server.py
```

Documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
