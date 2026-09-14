"""Layer 2 -- DEM/hydrological detection (plan.md stage 4), blind
reproduction of Dai et al. 2023's method (no reply yet from outreach,
see constitution.md's outreach-first-but-don't-block-forever decision).

Method (reproduced from the paper's abstract/description, not their
code): a check dam interrupts a stream's natural longitudinal profile,
creating an artificially flat, ponded reach immediately upstream of a
sharp elevation drop at the structure itself. This shows up as a
"step" anomaly in the along-stream elevation profile -- a segment
noticeably flatter than its surroundings, immediately followed by a
steeper-than-average drop.

Pipeline: fill depressions -> flow direction/accumulation -> extract
stream network above a flow-accumulation threshold -> walk each stream
reach in flow order -> flag step anomalies via a sliding-window slope
comparison.
"""

import glob
import json
import os

import numpy as np
import rasterio
import richdem as rd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEM_DIR = os.path.join(PROJECT_ROOT, "data/raw/dem_tiles")
OUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer2_dem_candidates.jsonl")

FLOW_ACCUM_THRESHOLD = 500  # cells (~1.25ha contributing area) to count as a stream
WINDOW = 6  # cells either side (~30m at 5m/px) for the slope comparison
FLAT_SLOPE_MAX = 0.015  # upstream window must be flatter than this (m/m) to qualify
STEP_SLOPE_MIN = 0.05  # downstream window must be steeper than this to count as a step
MIN_RATIO = 3.0  # downstream slope must be at least this many times the upstream slope


def analyze_tile(dem_path: str) -> list:
    with rasterio.open(dem_path) as src:
        elev = src.read(1).astype("float64")
        transform = src.transform
        nodata = src.nodata

    if nodata is not None:
        elev[elev == nodata] = np.nan
    if np.isnan(elev).all():
        return []

    dem = rd.rdarray(elev, no_data=-9999 if nodata is None else nodata)
    dem_filled = rd.FillDepressions(dem, epsilon=False, in_place=False)
    accum = rd.FlowAccumulation(dem_filled, method="D8")

    accum_arr = np.array(accum)
    stream_mask = accum_arr > FLOW_ACCUM_THRESHOLD
    stream_ys, stream_xs = np.where(stream_mask)
    if len(stream_ys) == 0:
        return []

    # richdem's build here has no standalone FlowDirection -- compute D8
    # steepest-descent ourselves from the (already depression-filled) DEM.
    elev_arr = np.array(dem_filled)
    d8_offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    d8_dist = [np.sqrt(2), 1, np.sqrt(2), 1, 1, np.sqrt(2), 1, np.sqrt(2)]

    def steepest_descent(y, x):
        best_drop, best_off = -np.inf, None
        for (dy, dx), dist in zip(d8_offsets, d8_dist):
            ny, nx = y + dy, x + dx
            if 0 <= ny < elev_arr.shape[0] and 0 <= nx < elev_arr.shape[1]:
                drop = (elev_arr[y, x] - elev_arr[ny, nx]) / dist
                if drop > best_drop:
                    best_drop, best_off = drop, (dy, dx)
        return best_off

    candidates = []
    visited = np.zeros_like(stream_mask, dtype=bool)

    for y0, x0 in zip(stream_ys, stream_xs):
        if visited[y0, x0]:
            continue
        # Walk downstream from this cell, building a profile.
        path = [(y0, x0)]
        y, x = y0, x0
        for _ in range(200):  # cap path length per seed to bound runtime
            off = steepest_descent(y, x)
            if off is None:
                break
            dy, dx = off
            ny, nx = y + dy, x + dx
            if not stream_mask[ny, nx]:
                break
            path.append((ny, nx))
            y, x = ny, nx
        for py, px in path:
            visited[py, px] = True

        if len(path) < 2 * WINDOW + 2:
            continue

        profile = np.array([elev_arr[py, px] for py, px in path])
        for i in range(WINDOW, len(profile) - WINDOW):
            upstream = profile[i - WINDOW : i]
            downstream = profile[i : i + WINDOW]
            up_slope = abs(upstream[0] - upstream[-1]) / WINDOW
            down_slope = abs(downstream[0] - downstream[-1]) / WINDOW
            if up_slope < FLAT_SLOPE_MAX and down_slope > STEP_SLOPE_MIN and down_slope > MIN_RATIO * max(up_slope, 1e-6):
                py, px = path[i]
                lon, lat = transform * (px, py)
                candidates.append(
                    {
                        "x": lon,
                        "y": lat,
                        "up_slope": round(up_slope, 4),
                        "down_slope": round(down_slope, 4),
                        "flow_accum": int(accum_arr[py, px]),
                    }
                )

    return candidates


if __name__ == "__main__":
    import sys

    files = sorted(glob.glob(f"{DEM_DIR}/*.tif"))
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if limit:
        files = files[:limit]
    print(f"Analyzing {len(files)} DEM tiles for check-dam-like step anomalies...")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    n_candidates = 0
    with open(OUT_PATH, "a") as out_f:
        for f in files:
            tile_id = os.path.basename(f).replace(".tif", "")
            try:
                candidates = analyze_tile(f)
            except Exception as e:
                print(f"  {tile_id}: failed ({e})")
                continue
            for c in candidates:
                out_f.write(json.dumps({"tile_id": tile_id, **c}) + "\n")
            n_candidates += len(candidates)
            print(f"  {tile_id}: {len(candidates)} step anomalies")

    print(f"\nTotal DEM step-anomaly candidates: {n_candidates}")
