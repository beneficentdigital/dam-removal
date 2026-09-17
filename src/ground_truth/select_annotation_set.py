"""Dedupe the merged ground truth and select a geographically-spread
sample for Layer 1 annotation (T018), holding out 20% for evaluation
only (FR-007a — never used in fine-tuning).
"""

import geopandas as gpd
import numpy as np
import pandas as pd

DEDUP_RADIUS_M = 50
N_ANNOTATE_TOTAL = 100
HOLDOUT_FRACTION = 0.2
GRID_CELLS_PER_SIDE = 10  # for spatial stratification
SOURCE_PRIORITY = {"SNCZI": 0, "DAM_OR_WEIR": 1, "ANDALUCIA_DERA": 2, "AMBER": 3, "OSM": 4}


def dedupe(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["_priority"] = gdf["source"].map(SOURCE_PRIORITY)
    gdf_m = gdf.to_crs(epsg=25830)
    kept_idx = []
    kept_geoms = []
    # Sort by priority so higher-priority sources are kept when clusters merge.
    for idx, row in gdf_m.sort_values("_priority").iterrows():
        pt = row.geometry
        if any(pt.distance(g) < DEDUP_RADIUS_M for g in kept_geoms):
            continue
        kept_idx.append(idx)
        kept_geoms.append(pt)
    return gdf.loc[kept_idx].drop(columns="_priority")


def stratified_sample(gdf: gpd.GeoDataFrame, n: int) -> gpd.GeoDataFrame:
    gdf_m = gdf.to_crs(epsg=25830)
    minx, miny, maxx, maxy = gdf_m.total_bounds
    cell_w = (maxx - minx) / GRID_CELLS_PER_SIDE
    cell_h = (maxy - miny) / GRID_CELLS_PER_SIDE
    gdf = gdf.copy()
    gx = ((gdf_m.geometry.x - minx) // cell_w).clip(upper=GRID_CELLS_PER_SIDE - 1)
    gy = ((gdf_m.geometry.y - miny) // cell_h).clip(upper=GRID_CELLS_PER_SIDE - 1)
    gdf["_cell"] = list(zip(gx.astype(int), gy.astype(int)))

    non_empty_cells = gdf["_cell"].unique()
    rng = np.random.default_rng(42)
    per_cell = max(1, n // len(non_empty_cells))
    picks = []
    for cell in non_empty_cells:
        candidates = gdf[gdf["_cell"] == cell]
        take = min(per_cell, len(candidates))
        picks.append(candidates.sample(take, random_state=42))
    result = pd.concat(picks)
    if len(result) > n:
        result = result.sample(n, random_state=rng.integers(1e6))
    return result.drop(columns="_cell")


if __name__ == "__main__":
    df = pd.read_csv("data/processed/ground_truth_guadalquivir.csv")
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")

    deduped = dedupe(gdf)
    print(f"Deduped (50m radius, source-priority kept): {len(gdf)} -> {len(deduped)}")

    sample = stratified_sample(deduped, N_ANNOTATE_TOTAL)
    print(f"Stratified sample selected: {len(sample)} across up to "
          f"{GRID_CELLS_PER_SIDE}x{GRID_CELLS_PER_SIDE} grid cells")

    n_holdout = round(len(sample) * HOLDOUT_FRACTION)
    holdout = sample.sample(n_holdout, random_state=7)
    training = sample.drop(holdout.index)

    training.drop(columns="geometry").to_csv(
        "data/processed/layer1_annotation_training_set.csv", index=False
    )
    holdout.drop(columns="geometry").to_csv(
        "data/processed/layer1_holdout_set.csv", index=False
    )
    print(f"Training (to annotate): {len(training)}")
    print(f"Held out (never used in fine-tuning, FR-007a): {len(holdout)}")
    print("\nSource breakdown of full sample:")
    print(sample["source"].value_counts())
