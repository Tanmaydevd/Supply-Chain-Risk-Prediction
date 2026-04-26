"""Train + benchmark three delay classifiers and persist the best one.

Run as a script:
    python -m ml.train_model

What it does:
    1. Loads data/processed/shipments.csv
    2. Trains LogisticRegression (baseline), RandomForestClassifier, and
       XGBClassifier (if installed)
    3. Prints a comparison table (accuracy, precision, recall, F1, ROC-AUC)
    4. Saves every model to trained_models/<name>.joblib
    5. Saves the *best* model (by F1) as trained_models/delay_rf.joblib
       — the canonical name that prediction_service.py loads.
    6. Saves feature importances to trained_models/feature_importances.csv
    7. Saves a markdown summary to trained_models/evaluation_report.md
"""
from __future__ import annotations
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from config import DATA_PROCESSED, MODELS_DIR, RANDOM_SEED
from ml.preprocess import feature_columns


# ---- model factory --------------------------------------------------------

def _candidate_models() -> dict:
    """Return the dict of name -> estimator we'll benchmark."""
    models: dict[str, object] = {
        "logreg": Pipeline(
            [("scaler", StandardScaler()),
             ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED))]
        ),
        "rf": RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
    }
    try:  # XGBoost is optional
        from xgboost import XGBClassifier  # type: ignore

        models["xgb"] = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.1,
            random_state=RANDOM_SEED,
            eval_metric="logloss",
            n_jobs=-1,
        )
    except ImportError:
        print("[train] xgboost not installed - skipping XGB benchmark.")

    try:  # CatBoost — paper §3.4.2: best overall AUC (72.4%-99.9%)
        from catboost import CatBoostClassifier  # type: ignore

        models["catboost"] = CatBoostClassifier(
            iterations=300,
            depth=6,
            learning_rate=0.1,
            random_seed=RANDOM_SEED,
            verbose=0,
            eval_metric="AUC",
        )
    except (ImportError, Exception):
        print("[train] catboost not installed - skipping CatBoost benchmark.")
    return models


# ---- evaluation -----------------------------------------------------------

def _score(model, Xte, yte) -> dict:
    yp = model.predict(Xte)
    yp_prob = (
        model.predict_proba(Xte)[:, 1]
        if hasattr(model, "predict_proba")
        else yp.astype(float)
    )
    return {
        "accuracy": accuracy_score(yte, yp),
        "precision": precision_score(yte, yp, zero_division=0),
        "recall": recall_score(yte, yp, zero_division=0),
        "f1": f1_score(yte, yp, zero_division=0),
        "roc_auc": roc_auc_score(yte, yp_prob),
        "confusion": confusion_matrix(yte, yp).tolist(),
    }


# ---- feature importance ---------------------------------------------------

def _feature_importance(model, feature_names: list[str]) -> pd.DataFrame:
    if hasattr(model, "feature_importances_"):  # RF, XGB
        imp = model.feature_importances_
    elif isinstance(model, Pipeline) and hasattr(model.named_steps["clf"], "coef_"):
        imp = np.abs(model.named_steps["clf"].coef_[0])
    else:
        return pd.DataFrame()
    return (
        pd.DataFrame({"feature": feature_names, "importance": imp})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


# ---- SHAP explainability (paper §3.5) ------------------------------------

def _compute_shap(model, model_name: str, Xte: pd.DataFrame, feature_names: list[str]) -> None:
    """Compute SHAP values for the winning model and save to trained_models/.

    Paper §3.5: SHAP values provide unified feature importance and enable
    step-wise feature selection (threshold 0.01) for each delivery step.
    """
    try:
        import shap  # type: ignore
    except ImportError:
        print("[train] shap not installed - skipping SHAP computation.")
        return

    try:
        # Unwrap Pipeline for tree-based explainer
        actual_model = model.named_steps["clf"] if hasattr(model, "named_steps") else model

        # Use TreeExplainer for tree models; KernelExplainer for linear
        if hasattr(actual_model, "estimators_") or hasattr(actual_model, "get_booster"):
            explainer = shap.TreeExplainer(actual_model)
            raw = explainer.shap_values(Xte)
        else:
            explainer = shap.KernelExplainer(
                model.predict_proba, shap.sample(Xte, min(50, len(Xte)))
            )
            raw = explainer.shap_values(Xte)

        # Normalize to 2-D array of shape (n_samples, n_features) for class=1
        if isinstance(raw, list):
            sv = np.array(raw[1])          # list[class0, class1]
        elif isinstance(raw, np.ndarray) and raw.ndim == 3:
            sv = raw[:, :, 1]              # (samples, features, classes)
        else:
            sv = np.array(raw)

        if sv.ndim != 2:
            raise ValueError(f"Unexpected SHAP shape {sv.shape}")

        # Mean |SHAP| per feature — paper §3.5 selection criterion (threshold 0.01)
        mean_abs = np.abs(sv).mean(axis=0)
        shap_df = (
            pd.DataFrame({"feature": feature_names, "shap_importance": mean_abs})
            .sort_values("shap_importance", ascending=False)
            .reset_index(drop=True)
        )
        shap_df.to_csv(MODELS_DIR / "shap_importances.csv", index=False)
        print("[train] SHAP importances (mean |shap|):")
        print(shap_df.to_string(index=False))

        selected = shap_df[shap_df.shap_importance >= 0.01]["feature"].tolist()
        print(f"[train] SHAP-selected features (>=0.01): {selected}")

        np.save(MODELS_DIR / "shap_values.npy", sv)
        np.save(MODELS_DIR / "shap_test_X.npy", Xte.values)
        (MODELS_DIR / "shap_feature_names.txt").write_text("\n".join(feature_names))
        print(f"[train] SHAP data saved to {MODELS_DIR}")

    except Exception as exc:
        print(f"[train] SHAP computation skipped ({exc})")


# ---- main -----------------------------------------------------------------

def train() -> dict:
    csv = DATA_PROCESSED / "shipments.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"{csv} not found. Run `python -m ml.preprocess` first."
        )
    df = pd.read_csv(csv)
    feats = feature_columns()
    X, y = df[feats], df["delayed"]

    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}

    for name, est in _candidate_models().items():
        est.fit(Xtr, ytr)
        results[name] = _score(est, Xte, yte)
        joblib.dump(est, MODELS_DIR / f"{name}.joblib")
        print(f"[train] {name:>6}  F1={results[name]['f1']:.3f}  "
              f"acc={results[name]['accuracy']:.3f}  "
              f"AUC={results[name]['roc_auc']:.3f}")

    # pick the best by F1
    best_name = max(results, key=lambda k: results[k]["f1"])
    best_model = joblib.load(MODELS_DIR / f"{best_name}.joblib")

    # canonical alias used by prediction_service.py
    joblib.dump(best_model, MODELS_DIR / "delay_rf.joblib")
    print(f"[train] best = {best_name} -> saved as delay_rf.joblib")

    # feature importance for the winning model (native)
    fi = _feature_importance(best_model, feats)
    if not fi.empty:
        fi.to_csv(MODELS_DIR / "feature_importances.csv", index=False)
        print("[train] feature importances (native):")
        print(fi.to_string(index=False))

    # SHAP values — paper §3.5: used for feature selection + explainability
    _compute_shap(best_model, best_name, Xte, feats)

    # summary report (markdown, copyable into the project doc)
    rep_md = MODELS_DIR / "evaluation_report.md"
    with rep_md.open("w") as f:
        f.write("# Model evaluation report\n\n")
        f.write(f"Best model (by F1): **{best_name}**\n\n")
        f.write("| model | accuracy | precision | recall | F1 | ROC-AUC |\n")
        f.write("|---|---|---|---|---|---|\n")
        for n, r in results.items():
            f.write(
                f"| {n} | {r['accuracy']:.3f} | {r['precision']:.3f} | "
                f"{r['recall']:.3f} | {r['f1']:.3f} | {r['roc_auc']:.3f} |\n"
            )
        f.write("\n## Confusion matrices\n\n")
        for n, r in results.items():
            f.write(f"### {n}\n```\n{r['confusion']}\n```\n\n")
        if not fi.empty:
            f.write("## Feature importances (winner)\n\n")
            f.write("| feature | importance |\n|---|---|\n")
            for _, row in fi.iterrows():
                f.write(f"| {row.feature} | {row.importance:.3f} |\n")
    print(f"[train] wrote {rep_md}")

    # JSON for programmatic loading on the Analytics page
    (MODELS_DIR / "metrics.json").write_text(
        json.dumps({"best": best_name, "results": results}, indent=2)
    )
    return {"best": best_name, "results": results, "model": best_model}


if __name__ == "__main__":
    train()
