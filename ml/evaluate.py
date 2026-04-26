"""Standalone evaluation utility: prints metrics for an already-trained model."""
from __future__ import annotations
import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from config import DATA_PROCESSED, MODELS_DIR, RANDOM_SEED
from ml.preprocess import feature_columns


def evaluate() -> None:
    model = joblib.load(MODELS_DIR / "delay_rf.joblib")
    df = pd.read_csv(DATA_PROCESSED / "shipments.csv")
    X, y = df[feature_columns()], df["delayed"]
    _, Xte, _, yte = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )
    yp = model.predict(Xte)
    print(classification_report(yte, yp, digits=3))
    print("Confusion matrix:\n", confusion_matrix(yte, yp))


if __name__ == "__main__":
    evaluate()
