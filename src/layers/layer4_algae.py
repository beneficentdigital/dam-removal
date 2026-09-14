"""Layer 4 -- ecological/algae confirming signal (plan.md stage 6), via
CyFi (Cyanobacteria Finder). Per the plan, this runs near existing
candidates from Layers 1/3, not as an independent basin-wide scan --
CyFi's per-point cost (imagery search + land cover lookup) makes a
blind scan wasteful when we already have candidate locations to check.

Runs in .venv-owm (Python 3.11) -- CyFi needs 3.10+, same as
OmniWaterMask. Uses CyFi's batch `predict` command (one CSV in, one CSV
out) rather than looping predict-point calls, since batch mode shares
setup cost (land cover lookups, imagery search) across all points.
"""

import os
import subprocess
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENV_CYFI = os.path.join(PROJECT_ROOT, ".venv-owm/bin/cyfi")


def run_cyfi_batch(points_df: pd.DataFrame, date: str, out_dir: str) -> pd.DataFrame:
    """points_df needs 'lat' and 'lon' columns. Adds a fixed date to
    each (CyFi wants one per point; a single representative summer date
    is a reasonable default for a confirming signal, not a time series)."""
    os.makedirs(out_dir, exist_ok=True)
    sample_path = os.path.join(out_dir, "sample_points.csv")
    out_path = os.path.join(out_dir, "preds.csv")

    samples = points_df[["lat", "lon"]].copy()
    samples["date"] = date
    samples = samples.rename(columns={"lat": "latitude", "lon": "longitude"})
    samples.to_csv(sample_path, index=False)

    subprocess.run(
        [VENV_CYFI, "predict", sample_path, "-d", out_dir, "-f", "preds.csv", "--overwrite"],
        check=True,
    )
    return pd.read_csv(out_path)


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/processed/micro_pilot_ground_truth.csv"
    date = sys.argv[2] if len(sys.argv) > 2 else "2024-06-15"
    out_dir = os.path.join(PROJECT_ROOT, "data/raw/layer4_cyfi")

    df = pd.read_csv(os.path.join(PROJECT_ROOT, csv_path))
    print(f"Running CyFi on {len(df)} points from {csv_path}, date={date}...")

    results = run_cyfi_batch(df, date, out_dir)
    print(results[["latitude", "longitude", "density_cells_per_ml", "severity"]])

    out_path = os.path.join(PROJECT_ROOT, "data/processed/layer4_algae_results.csv")
    results.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")
    print(results["severity"].value_counts())
