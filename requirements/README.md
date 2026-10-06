# GridMind AI — Modular Requirements Architecture

This directory separates project dependencies by environment and responsibility.

## Directory Structure

```
requirements/
├── base.txt       # Core FastAPI backend, schemas, server, and networking
├── ml.txt         # Data science, Scikit-Learn, Statsmodels, Prophet, Matplotlib
├── dev.txt        # Testing (pytest, httpx) and code quality (black, flake8)
├── prod.txt       # Production database (MongoDB) and streaming (Kafka)
├── optional.txt   # Optional ML extensions (XGBoost, TensorFlow, PyYAML)
└── README.md      # This guide
```

## Installation Guide

### 1. Standard Installation (Recommended for Local App & Dashboard)
Installs core backend and machine learning pipelines:
```bash
pip install -r requirements/base.txt -r requirements/ml.txt
```
*(Or use the root `pip install -r requirements.txt`)*

### 2. Development & Testing
Installs backend, ML models, and testing suites (pytest, httpx):
```bash
pip install -r requirements/dev.txt
```

### 3. Production Deployment
Installs full stack including MongoDB connector and Kafka:
```bash
pip install -r requirements/prod.txt
```

### 4. Optional Deep Learning Extensions
For experimental neural network and gradient boosting models:
```bash
pip install -r requirements/optional.txt
```
