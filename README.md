# Supply Chain Risk Intelligence

AI-powered logistics decision-support system: predicts shipment delays, scores network risk, simulates cascading failures, and recommends alternate routes.

> Read **`DESIGN.md`** first — it is the full step-by-step build playbook.

## Quickstart (one command)

```bash
# 1. Setup (Windows)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Build everything (data + EDA + train all models)
python run_pipeline.py

# 3. Launch the dashboard
streamlit run app/Home.py
```

The dashboard opens at http://localhost:8501.

## Manual / step-by-step (same thing, broken out)

```bash
python -m ml.preprocess     # generate synthetic shipments
python -m ml.eda            # print + save EDA summary
python -m ml.train_model    # benchmark LogReg + RF (+ XGB), save best
streamlit run app/Home.py
```

## Tests

```bash
pytest tests/ -v
```

## Project structure

| Folder | Purpose |
|---|---|
| `data/` | Raw + processed CSVs (nodes, edges, shipments, eda_summary.md) |
| `ml/` | preprocess, train_model (multi-model benchmark), eda, olist_loader |
| `graph/` | NetworkX graph builder, analytics, simulation, routing |
| `services/` | Pure-Python facade used by the UI (no Streamlit imports here) |
| `app/` | Streamlit multi-page dashboard with reusable components |
| `trained_models/` | Saved `.joblib` models + `evaluation_report.md` + `metrics.json` |
| `tests/` | pytest suite + `scenarios.md` (manual demo scenarios) |

## Models trained

`run_pipeline.py` benchmarks three models and saves the winner as `trained_models/delay_rf.joblib`:

| name | type | notes |
|---|---|---|
| `logreg` | Logistic Regression (with StandardScaler) | Sanity baseline |
| `rf` | Random Forest (200 trees) | Default winner |
| `xgb` | XGBoost (300 rounds) | Skipped silently if `xgboost` isn't installed |

Comparison metrics + confusion matrices are written to `trained_models/evaluation_report.md`.

## Optional: Real shipment data (Olist, Stage C)

```bash
# Download Olist CSVs into data/raw/olist/
python -m ml.olist_loader
# To merge with the synthetic shipments and retrain:
python -c "from ml.olist_loader import merge_with_synthetic; merge_with_synthetic()"
python -m ml.train_model
```

See `DESIGN.md` §6.3 for caveats — Olist cities are Brazilian, mapped to our 15-city graph by hashing.
