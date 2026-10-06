# GridMind AI — Intelligent Smart Energy & Power Failure System

Real-Time Smart Energy Consumption & Power Failure Prediction System for TGSPDCL/TGNPDCL.
Production-ready full-stack system featuring an interactive **Operations Web Dashboard (Frontend)**, a modular **FastAPI REST Backend**, and trained **Machine Learning Models**.

## 🚀 Quick Launch (Frontend + Backend)

Simply run the one-click batch launcher or Python:

```bash
# Option 1: Double-click or run:
start_dashboard.bat

# Option 2: Run with Python:
python run_server.py
```

- **Frontend Operations Dashboard**: [http://localhost:8000](http://localhost:8000)
- **FastAPI Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc Docs**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🖥️ What's New: Interactive Frontend Dashboard

A responsive, state-of-the-art Operations Center web UI built with HTML5, CSS3 (Cyber-Grid Theme with Dark/Light mode), and Chart.js:
1. **Executive Overview**: Real-time KPIs, historical telemetry volume (156k+ rows), 16 distribution circles, 5.0% anomaly rate, and system health status.
2. **Disruption & Power Failure Predictor**: Interactive testing form with one-click presets (High Risk Overload, Normal Residential, Heavy Industrial, Subsidized Agricultural), live feature calculation, animated risk gauge, and AI dispatch recommendations.
3. **Smart Meter Anomaly Detector**: Isolation Forest live scanning console for detecting power theft, meter bypasses, or hardware faults with score threshold visualizer.
4. **Energy Demand Forecasting**: Multi-step SARIMA and Prophet projection chart with interactive horizon slider (3 to 18 months) and detailed monthly kWh/MWh breakdown table.
5. **Grid Circles & Clusters**: Interactive K-Means (k=4) bubble chart and sortable table comparing all 16 TGSPDCL/TGNPDCL circles by load factor and disruption rate.
6. **Kafka Telemetry Stream Simulator**: Real-time IoT smart meter stream processing simulation through the ML scoring pipeline with an animated packet terminal and live alert feed.
7. **Model Analytics & Reports**: Live metrics table and embedded 4-panel high-resolution analytics dashboard report (`gridmind_dashboard.png`).

---

## 🛡️ Role-Based Access Control (RBAC) & Security Architecture

When the application opens in your web browser, it is guarded by a **Security Access Gateway** enforcing cryptographic Role-Based Access Control (RBAC):

### 👥 Configured Administrative Roles & Credentials

| Role | Username | Default Password | Access Level & Scope |
| :--- | :--- | :--- | :--- |
| **⚡ Super Admin (You)** | `admin` | `admin123` | **Full Root Authority**: Unrestricted access to all grid prediction models, SARIMA forecasting, circle clusters, Kafka live stream simulation, security administration, user roster, and audit trails. |
| **🛡️ Security Admin 1 (SOC Lead)** | `sec_admin1` | `secadmin1` | **Security Operations Lead**: Specialized in smart meter anomaly audits, threat & tamper monitoring, Kafka stream audit executions, and real-time security incident logs. |
| **🛡️ Security Admin 2 (Grid Safety)** | `sec_admin2` | `secadmin2` | **Disaster & Safety Compliance Officer**: Focuses on disruption probabilities, failure alert thresholds, emergency failover oversight, and regulatory audit review. |
| **📊 Grid Operator** | `operator` | `operator123` | **Operations Analyst**: Read-only access to operational dashboards and basic prediction queries; blocked from stream simulation and security logs. |

*Alternate passwords accepted for testing:* `GridAdmin@2026!` (for admin), `SecAdmin1@2026!` (for sec_admin1), `SecAdmin2@2026!` (for sec_admin2).

### 🔐 Security & Cryptography Specifications
- **Password Protection**: Industry-standard **PBKDF2-HMAC-SHA256** with 100,000 hashing iterations and unique 16-byte cryptographically secure random salt.
- **Session Tokens**: Tamper-proof **HMAC-SHA256 (HS256)** signed Bearer tokens with 24-hour expiration and constant-time signature verification.
- **Audit Ledger**: Chronological immutable security audit trail logging every login attempt, logout, privilege check, and live Kafka simulation trigger.
- **Browser Security Gateway**: Interactive login modal with one-click **Fast Role Selector** pills for rapid verification during demonstrations.

---

## Project Structure

```
GridMind-AI/
├── frontend/                   # Interactive Web UI (HTML5, CSS3, Chart.js)
│   ├── index.html              # Operations Dashboard Single Page App
│   ├── css/style.css           # Cyber-Grid responsive stylesheet & theme
│   └── js/
│       ├── app.js              # API client, live stream animation & form logic
│       └── charts.js           # Chart.js visualization handlers
├── app/                        # FastAPI Backend Package
│   ├── main.py                 # FastAPI app entrypoint & static mounting
│   ├── schemas.py              # Pydantic request/response models
│   ├── core/                   # Settings, logging, and environment configuration
│   ├── services/               # ML pipeline, model registry, cache, MongoDB
│   └── routers/                # REST endpoints: health, predict, stream, dashboard, data, evaluate
├── data/                       # 17 monthly CSV telemetry files (156k+ rows)
├── models/                     # Trained ML models (.pkl): RF, Isolation Forest, SARIMA, KMeans
├── reports/                    # evaluation_summary.json, training_summary.json, dashboard PNG
├── notebooks/                  # Original exploratory data analysis notebook
├── requirements/               # Modular dependency sets (base, ml, dev, prod)
│   ├── base.txt                # Core FastAPI backend & server dependencies
│   ├── ml.txt                  # Data science, Scikit-Learn, Statsmodels, Prophet
│   ├── dev.txt                 # Testing (pytest, httpx) & linting tools
│   ├── prod.txt                # Production database & Kafka streaming
│   ├── optional.txt            # Deep learning & future model extensions
│   └── README.md               # Requirements guide & install options
├── start_dashboard.bat         # Windows 1-click launcher
├── run_server.py               # Python unified launcher (starts API & opens browser)
├── train_pipeline.py           # Model training pipeline
├── evaluate_pipeline.py        # Model evaluation suite
├── generate_reports.py         # Matplotlib report generator
├── test_auth_rbac.py           # Automated test suite for RBAC & authentication
├── test_server_live.py         # Live server end-to-end integration test suite
└── requirements.txt            # Master requirements linker
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
