"""One-command bootstrap: data -> EDA -> training.

Usage:
    python run_pipeline.py              # synthetic data only (fast, offline)
    python run_pipeline.py --real       # merge real e-commerce data then train

Real data setup (one time):
    python -m ml.ecommerce_loader --download   # needs kaggle.json credentials
    python run_pipeline.py --real

After this, launch the dashboard with:
    streamlit run app/Home.py
"""
from __future__ import annotations
import sys
import time

USE_REAL = "--real" in sys.argv


def step(name: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n[ {name} ]\n{bar}")


def main() -> int:
    t0 = time.time()
    n_steps = 4 if USE_REAL else 3
    try:
        step(f"1/{n_steps}  Generating synthetic shipments")
        from ml.preprocess import generate_synthetic_shipments
        generate_synthetic_shipments()

        if USE_REAL:
            step(f"2/{n_steps}  Merging real e-commerce shipment data")
            from ml.ecommerce_loader import load_ecommerce, merge_with_synthetic
            load_ecommerce()
            merge_with_synthetic()

        step(f"{'3' if USE_REAL else '2'}/{n_steps}  Running EDA")
        from ml.eda import run as run_eda
        run_eda()

        step(f"{'4' if USE_REAL else '3'}/{n_steps}  Training + benchmarking models")
        from ml.train_model import train
        out = train()

        elapsed = time.time() - t0
        print(f"\n[OK] Pipeline complete in {elapsed:.1f}s. Best model: {out['best']}")
        if USE_REAL:
            print("     Trained on: synthetic + real e-commerce shipments")
        print("\nLaunch the dashboard:")
        print("    streamlit run app/Home.py")
        return 0
    except Exception as e:  # pragma: no cover
        print(f"\n[FAILED] Pipeline failed: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main())
