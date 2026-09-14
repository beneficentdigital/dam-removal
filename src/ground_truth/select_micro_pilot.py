"""Select ground-truth records within the micro-pilot box (spec.md) and
build a small annotation set from them -- reuses the same dedup logic
as the full-basin selection, just scoped to a tiny area for speed.
"""

import os

import geopandas as gpd
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOX_25830 = (287195.19, 4163964.80, 302195.19, 4178964.80)  # from spec.md
DEDUP_RADIUS_M = 50
HOLDOUT_FRACTION = 0.2
SOURCE_PRIORITY = {"SNCZI": 0, "ANDALUCIA_DERA": 1, "AMBER": 2, "OSM": 3}


def dedupe(gdf_m: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf_m.copy()
    gdf["_priority"] = gdf["source"].map(SOURCE_PRIORITY)
    kept_idx, kept_geoms = [], []
    for idx, row in gdf.sort_values("_priority").iterrows():
        pt = row.geometry
        if any(pt.distance(g) < DEDUP_RADIUS_M for g in kept_geoms):
            continue
        kept_idx.append(idx)
        kept_geoms.append(pt)
    return gdf.loc[kept_idx].drop(columns="_priority")


if __name__ == "__main__":
    df = pd.read_csv(os.path.join(PROJECT_ROOT, "data/processed/ground_truth_guadalquivir.csv"))
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")
    gdf_m = gdf.to_crs(epsg=25830)

    minx, miny, maxx, maxy = BOX_25830
    in_box = gdf_m.cx[minx:maxx, miny:maxy]
    print(f"Records in micro-pilot box: {len(in_box)}")
    print(in_box["source"].value_counts())

    deduped = dedupe(in_box)
    print(f"\nDeduped (50m radius): {len(in_box)} -> {len(deduped)}")

    n_holdout = max(1, round(len(deduped) * HOLDOUT_FRACTION))
    holdout = deduped.sample(n_holdout, random_state=7)
    training = deduped.drop(holdout.index)

    out_dir = os.path.join(PROJECT_ROOT, "data/processed")
    training.drop(columns="geometry").to_crs(epsg=4326) if False else None
    training_wgs = training.set_geometry(training.geometry).to_crs(epsg=4326)
    holdout_wgs = holdout.set_geometry(holdout.geometry).to_crs(epsg=4326)
    training_wgs.drop(columns="geometry").to_csv(f"{out_dir}/micro_pilot_training_set.csv", index=False)
    holdout_wgs.drop(columns="geometry").to_csv(f"{out_dir}/micro_pilot_holdout_set.csv", index=False)
    deduped.set_geometry(deduped.geometry).to_crs(epsg=4326).drop(columns="geometry").to_csv(
        f"{out_dir}/micro_pilot_ground_truth.csv", index=False
    )

    print(f"\nTraining (to annotate): {len(training)}")
    print(f"Held out: {len(holdout)}")
