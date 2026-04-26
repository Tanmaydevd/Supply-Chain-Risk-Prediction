"""Exploratory data analysis — prints insights and writes a markdown summary.

Run as a script:
    python -m ml.eda

Outputs:
    data/processed/eda_summary.md   (paste into your project report appendix)
"""
from __future__ import annotations
import pandas as pd

from config import DATA_PROCESSED
from ml.preprocess import feature_columns


def run() -> str:
    csv = DATA_PROCESSED / "shipments.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"{csv} not found. Run `python -m ml.preprocess` first."
        )
    df = pd.read_csv(csv)
    feats = feature_columns()

    out_lines: list[str] = ["# EDA Summary\n"]
    out_lines.append(f"Total shipments: **{len(df):,}**\n")
    out_lines.append(f"Overall delay rate: **{df['delayed'].mean():.1%}**\n")

    # delay rate by weather / traffic
    out_lines.append("## Delay rate by weather\n")
    by_w = df.groupby("weather_score")["delayed"].mean()
    out_lines.append(by_w.rename({0: "Sunny/Cloudy", 1: "Rain", 2: "Storm"}).to_markdown())
    out_lines.append("")

    out_lines.append("## Delay rate by traffic\n")
    by_t = df.groupby("traffic_score")["delayed"].mean()
    out_lines.append(by_t.rename({0: "Low", 1: "Medium", 2: "High"}).to_markdown())
    out_lines.append("")

    # warehouse load buckets
    out_lines.append("## Delay rate by warehouse load bucket\n")
    df["_load_bucket"] = pd.cut(
        df["warehouse_load"],
        bins=[0, 0.5, 0.7, 0.85, 1.0],
        labels=["light(<0.5)", "moderate(.5-.7)", "high(.7-.85)", "overload(>.85)"],
    )
    by_l = df.groupby("_load_bucket", observed=True)["delayed"].mean()
    out_lines.append(by_l.to_markdown())
    out_lines.append("")

    # top 10 risky routes (by empirical delay rate)
    out_lines.append("## Top 10 empirical-delay routes\n")
    by_r = (
        df.groupby(["origin", "destination"])
        .agg(n=("delayed", "size"), delay_rate=("delayed", "mean"))
        .reset_index()
        .query("n >= 20")
        .sort_values("delay_rate", ascending=False)
        .head(10)
    )
    out_lines.append(by_r.to_markdown(index=False))
    out_lines.append("")

    # correlations with delay
    out_lines.append("## Feature correlation with delay\n")
    corr = df[feats + ["delayed"]].corr()["delayed"].drop("delayed").sort_values(
        ascending=False
    )
    out_lines.append(corr.to_frame("correlation_with_delay").to_markdown())
    out_lines.append("")

    # class balance
    out_lines.append("## Class balance\n")
    out_lines.append(
        df["delayed"].value_counts().rename({0: "on-time", 1: "delayed"}).to_markdown()
    )
    out_lines.append("")

    md = "\n".join(out_lines)
    out = DATA_PROCESSED / "eda_summary.md"
    out.write_text(md)
    print(md)
    print(f"\n[eda] wrote {out}")
    return md


if __name__ == "__main__":
    run()
