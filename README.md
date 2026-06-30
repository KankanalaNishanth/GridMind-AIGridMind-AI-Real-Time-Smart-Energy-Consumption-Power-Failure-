# GridMind AI

GridMind AI is a real-time smart energy analytics platform for electricity consumption monitoring, outage-risk prediction, demand forecasting, anomaly detection, and historical grid reporting.

The project uses the requested stack without Docker for this first version:

- Backend: Python, FastAPI
- Database: MongoDB
- Streaming: Apache Kafka with `kafka-python`
- Frontend: HTML, CSS, JavaScript, Chart.js
- Machine Learning: XGBoost, Isolation Forest, optional LSTM and Prophet training
- Data: Telangana electricity CSV files copied into `data/raw`

## Project Structure

```text
GridmindAI/
  backend/app/              FastAPI application, APIs, MongoDB services
  data/raw/                 Source Telangana CSV files
  data/processed/           Normalized telemetry generated from CSVs
  frontend/                 Dashboard built with HTML, CSS, JavaScript, Chart.js
  ml/                       Data preprocessing and model training
  models/                   Trained model artifacts
  scripts/                  Local development stream simulator
  streaming/                Kafka producer and consumer
  tests/                    Focused preprocessing tests
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Start MongoDB locally before running the API. Start Kafka locally when using the Kafka producer and consumer.

## Train Models

```powershell
python -m ml.train
```

This command reads `data/raw/*.csv`, creates `data/processed/telemetry.csv`, trains the demand forecasting model and anomaly detector, and writes artifacts to `models/`.

The Telangana dataset contains aggregate electricity service/load records. The preprocessing layer converts those records into timestamped telemetry by deriving voltage, current, frequency, temperature, device status, and outage labels from load, consumption, and service utilization.

By default, the trainer uses the first 20,000 normalized records for fast local model creation and keeps the full processed dataset for streaming. Increase or disable that cap with `--max-training-rows`.

Optional LSTM and Prophet artifacts can be trained with:

```powershell
python -m ml.train --train-deep-models
```

## Run the API and Dashboard

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open the dashboard at:

```text
http://127.0.0.1:8000
```

Useful API endpoints:

- `GET /api/health`
- `POST /api/telemetry`
- `GET /api/dashboard`
- `GET /api/telemetry/recent`
- `GET /api/alerts`
- `GET /api/reports/history`
- `WS /api/ws`

## Stream Data Without Kafka

Use this during development when Kafka is not running:

```powershell
python -m scripts.run_local_stream --limit 200 --delay 0.4
```

## Stream Data With Kafka

Terminal 1:

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2:

```powershell
python -m streaming.consumer --api-url http://127.0.0.1:8000
```

Terminal 3:

```powershell
python -m streaming.producer --limit 500 --delay 0.2
```

## Notes

- Docker and Kubernetes are intentionally excluded from this version.
- If TensorFlow or Prophet is unavailable on your machine, the core project still works with XGBoost and Isolation Forest.
- The frontend receives live updates through FastAPI WebSockets and refreshes aggregate charts through REST APIs.
