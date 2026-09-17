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
import time

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENV_CYFI = os.path.join(PROJECT_ROOT, ".venv-owm/bin/cyfi")
CHUNK_SIZE = 15  # a full 816-point batch hit Microsoft Planetary Computer's
# STAC rate limit almost immediately (2026-09-16) -- CyFi's batch mode has
# no backoff/retry of its own, so it just crashed with nothing written.
RETRY_DELAYS_S = [30, 120, 300]  # backoff on a rate-limit hit, per chunk


def run_cyfi_chunk(chunk_df: pd.DataFrame, date: str, out_dir: str, chunk_name: str) -> pd.DataFrame:
    sample_path = os.path.join(out_dir, f"sample_{chunk_name}.csv")
    out_name = f"preds_{chunk_name}.csv"
    out_path = os.path.join(out_dir, out_name)

    samples = chunk_df[["lat", "lon"]].copy()
    samples["date"] = date
    samples = samples.rename(columns={"lat": "latitude", "lon": "longitude"})
    samples.to_csv(sample_path, index=False)

    subprocess.run(
        [VENV_CYFI, "predict", sample_path, "-d", out_dir, "-f", out_name, "--overwrite"],
        check=True,
        capture_output=True,
        text=True,
    )
    return pd.read_csv(out_path)


def run_cyfi_batch(points_df: pd.DataFrame, date: str, out_dir: str) -> pd.DataFrame:
    """points_df needs 'lat' and 'lon' columns. Adds a fixed date to
    each (CyFi wants one per point; a single representative summer date
    is a reasonable default for a confirming signal, not a time series).

    Resumable and rate-limit-tolerant: processes CHUNK_SIZE points at a
    time, checkpointing each chunk's own preds_<n>.csv so a crash loses
    at most one chunk, skips chunks whose output already exists on a
    rerun, and backs off + retries a chunk that hits a rate limit rather
    than taking the whole run down with it (constitution.md principle 3)."""
    os.makedirs(out_dir, exist_ok=True)
    points_df = points_df.reset_index(drop=True)
    n_chunks = (len(points_df) + CHUNK_SIZE - 1) // CHUNK_SIZE

    all_results = []
    for i in range(n_chunks):
        chunk_name = f"{i:04d}"
        out_path = os.path.join(out_dir, f"preds_{chunk_name}.csv")
        if os.path.exists(out_path):
            all_results.append(pd.read_csv(out_path))
            continue

        chunk_df = points_df.iloc[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE]
        print(f"chunk {i+1}/{n_chunks} ({len(chunk_df)} points)...")

        for attempt, delay in enumerate([0] + RETRY_DELAYS_S):
            if delay:
                print(f"  retrying after rate limit, waiting {delay}s...")
                time.sleep(delay)
            try:
                result = run_cyfi_chunk(chunk_df, date, out_dir, chunk_name)
                all_results.append(result)
                break
            except subprocess.CalledProcessError as e:
                if "rate limit" in (e.stderr or "").lower() and attempt < len(RETRY_DELAYS_S):
                    continue
                print(f"  chunk {chunk_name} failed, not rate-limit or out of retries: {e.stderr[-500:] if e.stderr else e}")
                break

    if not all_results:
        return pd.DataFrame()
    return pd.concat(all_results, ignore_index=True)


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
