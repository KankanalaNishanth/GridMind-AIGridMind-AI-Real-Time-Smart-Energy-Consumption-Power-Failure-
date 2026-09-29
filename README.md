# GridMind AI — Backend & ML API

Real-Time Smart Energy Consumption & Power Failure Prediction System for TGSPDCL/TGNPDCL.
Production-structured rewrite of the original `GridMind_AI_EndToEnd.ipynb` notebook — same
models, same feature engineering, same numbers, now organized as a runnable FastAPI service.

## What changed vs. the notebook

| Notebook | This project |
|---|---|
| Everything in one `.ipynb`, run cell by cell | Modular `app/` package, run as scripts/server |
| `!pip install ...` cell | `requirements.txt` |
| Hardcoded `file_*.csv` path in cwd | Configurable `data/` dir via `.env` |
| Models trained + used in the same session | `train_pipeline.py` trains & saves once; API loads from disk |
| FastAPI code generated as a string and written to `main.py` | Real `app/` package with routers, schemas, DB layer |
| Kafka/Mongo mentioned inline | MongoDB wired through `app/services/db.py`; Kafka producer/consumer is a future extension point (not required to run the API) |
| Plots shown inline | Not part of the API — re-run the original notebook in `notebooks/` if you want the EDA charts |

The feature engineering (`billing_ratio`, `avg_units_per_conn`, `load_factor`, `disruption`,
`season`) and every model's hyperparameters are unchanged, so results match the notebook
exactly (verified: 7,815 anomalies / 5.0%, RF ROC-AUC 1.0000, SARIMA MAPE 23.34%, KMeans
silhouette 0.2610 on this dataset).

## Phase coverage (mapped from the original notebook)

| Notebook Phase | This project |
|---|---|
| 1–2 Setup, Load & Clean Data | `app/services/data_loader.py` |
| 3 EDA | Original notebook (`notebooks/`) — not re-served by the API |
| 4–7 Anomaly / Disruption / Forecast / Clustering models | `app/services/ml_pipeline.py` (run via `train_pipeline.py`) |
| 8 Model Evaluation & Saving | `app/services/evaluation.py` (run via `evaluate_pipeline.py`) |
| 9 Kafka Simulation (Producer/Consumer) | `app/services/kafka_stream.py` + `POST /api/v1/stream/simulate` |
| 10 FastAPI Backend | `app/main.py` + `app/routers/*` (the whole `app/` package) |
| 11 Final Summary Dashboard | `app/services/dashboard_report.py` (run via `generate_reports.py`), served at `GET /api/v1/dashboard/image` |

## Project structure

```
gridmind-ai/
├── app/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── schemas.py              # Pydantic request/response models
│   ├── core/
│   │   ├── config.py           # Settings (reads .env)
│   │   └── logging_config.py
│   ├── services/
│   │   ├── data_loader.py      # CSV loading + feature engineering
│   │   ├── ml_pipeline.py      # Trains & saves all 5 models
│   │   ├── model_registry.py   # Loads trained models into memory at startup
│   │   └── db.py               # MongoDB connection
│   └── routers/
│       ├── health.py           # GET  /api/v1/health
│       ├── predict.py          # POST /api/v1/predict/disruption, /anomaly, GET /forecast
│       ├── data.py             # GET  /api/v1/data/consumption, /alerts  (Mongo-backed)
│       └── dashboard.py        # GET  /api/v1/dashboard/clusters, /summary
├── data/                       # Your file_*.csv monthly exports go here
├── models/                     # Trained model artifacts (.pkl) — generated, not hand-written
├── reports/                    # training_summary.json after each training run
├── notebooks/                  # Original notebook, kept for reference/EDA
├── train_pipeline.py           # Run this first — trains and saves every model
├── requirements.txt
├── .env.example                # Copy to .env and adjust
└── .vscode/                    # Pre-configured run/debug buttons
```

## Prerequisites

- Python 3.10+ (project was verified on 3.12)
- VS Code with the **Python** extension
- MongoDB running locally (or update `MONGO_URI` in `.env` to point elsewhere) — the API
  will still start and serve predictions without it; only `/data/*` routes need it.

## Run it — step by step in VS Code

### 1. Open the project
`File > Open Folder...` → select the `gridmind-ai` folder.

### 2. Create and activate a virtual environment
Open a terminal in VS Code (`` Ctrl+` ``):

```bash
python -m venv venv

# Activate — Windows:
venv\Scripts\activate

# Activate — macOS/Linux:
source venv/bin/activate
```

Then in VS Code: `Ctrl+Shift+P` → **Python: Select Interpreter** → choose `./venv`.
(The included `.vscode/settings.json` already points here, so this is usually automatic.)

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> `prophet` can take a few minutes to build on some systems. If it fails, that's fine —
> the pipeline skips Prophet gracefully and still trains everything else. Comment it out
> of `requirements.txt` if you want to skip it entirely.

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` if your MongoDB URI, ports, or thresholds differ from the defaults.

### 5. Add your data
Your 17 `file_*.csv` monthly exports go in `data/` (already included in this delivery).
To refresh with new data later, just replace the CSVs in `data/` and re-run step 6.

### 6. Train the models

```bash
python train_pipeline.py
```

This loads every CSV, cleans + engineers features, trains Isolation Forest, Random Forest,
SARIMA (+ Prophet if installed), and KMeans, and saves everything to `models/`. Takes
under 15 seconds on this dataset. You'll see a summary like:

```
TRAINING COMPLETE in 9.1s
  Rows processed : 156294
  Circles        : 16
  RF ROC-AUC     : 1.0000
  Anomalies      : 7815 (5.0%)
  Saved to       : models/
```

*Or, in VS Code: open the "Run and Debug" panel (`Ctrl+Shift+D`) and pick "1. Train
Pipeline" from the dropdown, then press F5.*

### 7. Run the API server

```bash
uvicorn app.main:app --reload --port 8000
```

*Or in VS Code: "Run and Debug" → "2. Run API (uvicorn)" → F5.*

### 8. Evaluate the models (optional but recommended)

```bash
python evaluate_pipeline.py
```

Reloads every saved model and recomputes accuracy/ROC-AUC (Random Forest), anomaly
counts (Isolation Forest), MAE/RMSE/MAPE (SARIMA), and silhouette score (KMeans) —
exactly like the notebook's Phase 8. Writes `reports/evaluation_summary.json`, which
`GET /api/v1/evaluate/summary` then serves.

*Or in VS Code: "Run and Debug" → "3. Evaluate Models" → F5.*

### 9. Generate the visual reports / final dashboard (optional)

```bash
python generate_reports.py
```

Recreates the notebook's final 5-panel analytics dashboard (monthly trend, disruption
rate by circle, anomaly split, cluster scatter, SARIMA forecast) as
`reports/gridmind_dashboard.png`. Served live at `GET /api/v1/dashboard/image`.

*Or in VS Code: "Run and Debug" → "4. Generate Reports (Dashboard PNG)" → F5.*

### 10. Try it out
- Swagger UI (interactive docs): **http://localhost:8000/docs**
- Health check: **http://localhost:8000/api/v1/health**

Example request from Swagger UI or curl:

```bash
curl -X POST http://localhost:8000/api/v1/predict/disruption \
  -H "Content-Type: application/json" \
  -d '{"circle":"KAMAREDDY","units":10135,"load":90.964,"tot_services":146,"billed_services":132,"month_num":2}'
```

## API reference

| Method | Route | Description |
|---|---|---|
| GET | `/api/v1/health` | Service status, model/DB readiness |
| POST | `/api/v1/predict/disruption` | Disruption risk score for one reading |
| POST | `/api/v1/predict/anomaly` | Anomaly score for one reading |
| GET | `/api/v1/predict/forecast?steps=6` | N-month demand forecast (SARIMA) |
| GET | `/api/v1/dashboard/clusters` | Circle clusters (from KMeans) |
| GET | `/api/v1/dashboard/image` | Final analytics dashboard as a PNG |
| GET | `/api/v1/dashboard/summary` | Live totals from MongoDB |
| GET | `/api/v1/data/consumption?circle=X&limit=100` | Recent telemetry (MongoDB) |
| GET | `/api/v1/data/alerts?limit=50` | Recent alerts (MongoDB) |
| GET | `/api/v1/evaluate/summary` | Model evaluation metrics (accuracy, ROC-AUC, MAPE, silhouette) |
| POST | `/api/v1/stream/simulate?n=30` | Simulate a Kafka producer→consumer→ML scoring cycle |

## Common issues

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Re-run `pip install -r requirements.txt` with venv activated |
| `503 Model not loaded` from `/predict/*` | Run `python train_pipeline.py` first |
| `503` from `/data/*` or empty `/dashboard/summary` | MongoDB isn't running/reachable — check `MONGO_URI` in `.env` |
| `No CSV files matching 'file_*.csv'` | Put your monthly CSVs in `data/` |
| Prophet fails to install | Safe to skip — comment it out of `requirements.txt`; SARIMA still works |
| Wrong Python interpreter in VS Code | `Ctrl+Shift+P` → "Python: Select Interpreter" → pick `./venv` |

## Next steps / extension points

- **Real Kafka streaming**: `POST /api/v1/stream/simulate` currently replays sampled
  historical rows through an in-memory queue (`app/services/kafka_stream.py`). To go live,
  swap the `deque` producer/consumer for `kafka-python` Producer/Consumer objects against
  a real broker — the message shape and `consume_and_predict()` scoring logic stay the same.
- **Frontend dashboard**: none is included yet (by design, for this delivery). The
  `/api/v1/dashboard/*` and `/api/v1/predict/*` routes are ready to be consumed by a
  React/Vue app whenever you want one.
- **Retraining on a schedule**: wrap `train_pipeline.py` in a cron job / Airflow DAG for
  periodic retraining as new monthly files arrive.
