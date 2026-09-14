"""Match detection candidates against the assembled ground truth
(SNCZI, AMBER, Andalucia DERA, OSM -- 3,595 deduped records) within the
project's locked 30m tolerance (plan.md stage 8, FR-005).

This was a real gap: every layer so far only generates candidates,
none of them get cross-referenced against what we already know exists.
Without this, a manual image review has zero context -- "is this a
known dam I just can't see clearly, or genuinely new" is unanswerable
from pixels alone.
"""

import json
import os

import geopandas as gpd
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GROUND_TRUTH_PATH = os.path.join(PROJECT_ROOT, "data/processed/ground_truth_guadalquivir.csv")
MATCH_TOLERANCE_M = 30  # locked project-wide (constitution.md)


def load_ground_truth() -> gpd.GeoDataFrame:
    df = pd.read_csv(GROUND_TRUTH_PATH)
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")
    return gdf.to_crs(epsg=25830)


def match_candidates(candidates_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """candidates_gdf needs a geometry column (point or polygon) in any
    CRS with .crs set. Returns the input with match_status,
    matched_source, matched_source_id, matched_distance_m columns."""
    gt = load_ground_truth()
    cand_m = candidates_gdf.to_crs(epsg=25830).copy()
    cand_points = cand_m.geometry.centroid if not (cand_m.geometry.geom_type == "Point").all() else cand_m.geometry

    cand_buffered = gpd.GeoDataFrame(geometry=cand_points.buffer(MATCH_TOLERANCE_M), crs=cand_m.crs)
    cand_buffered["_cand_idx"] = cand_m.index

    joined = gpd.sjoin(gt, cand_buffered, how="inner", predicate="within")
    # For candidates matching multiple ground-truth records, keep the closest.
    if len(joined) > 0:
        joined["_dist"] = joined.geometry.distance(
            cand_points.loc[joined["_cand_idx"]].reset_index(drop=True).set_axis(joined.index)
        )
        best = joined.sort_values("_dist").drop_duplicates("_cand_idx", keep="first")
    else:
        best = joined

    cand_m["match_status"] = "new"
    cand_m["matched_source"] = None
    cand_m["matched_source_id"] = None
    cand_m["matched_distance_m"] = None
    for _, row in best.iterrows():
        idx = row["_cand_idx"]
        cand_m.loc[idx, "match_status"] = "known"
        cand_m.loc[idx, "matched_source"] = row["source"]
        cand_m.loc[idx, "matched_source_id"] = row["source_id"]
        cand_m.loc[idx, "matched_distance_m"] = round(row["_dist"], 1)

    return cand_m.drop(columns="geometry")


if __name__ == "__main__":
    import sys

    in_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else in_path.replace(".csv", "_matched.csv")

    df = pd.read_csv(in_path)
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")

    result = match_candidates(gdf)
    result.to_csv(out_path, index=False)
    print(f"Matched {len(result)} candidates:")
    print(result["match_status"].value_counts())
    print(f"Saved to {out_path}")
