"""Dedupe NDWI candidates before the expensive OmniWaterMask confirmation
pass -- the same water body can produce multiple nearby polygons (tile
edges, noisy fragmentation), and confirming each one separately would
waste a meaningful chunk of the ~50s/candidate OmniWaterMask cost.
"""

import json
import os

import geopandas as gpd
from shapely.geometry import shape

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IN_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer3_water_candidates.jsonl")
OUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer3_water_candidates_deduped.jsonl")
DEDUP_RADIUS_M = 50


def load_candidates(path):
    records = []
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            records.append(rec)
    return records


if __name__ == "__main__":
    records = load_candidates(IN_PATH)
    print(f"Loaded {len(records)} raw NDWI candidates")

    geoms = [shape(r["geometry"]) for r in records]
    gdf = gpd.GeoDataFrame(records, geometry=geoms, crs="EPSG:4326").to_crs(epsg=25830)

    # Sort by area descending so the largest fragment of a split water
    # body is kept as the representative.
    gdf["_area"] = gdf.geometry.area
    gdf = gdf.sort_values("_area", ascending=False)

    kept_idx, kept_geoms = [], []
    for idx, row in gdf.iterrows():
        centroid = row.geometry.centroid
        if any(centroid.distance(g) < DEDUP_RADIUS_M for g in kept_geoms):
            continue
        kept_idx.append(idx)
        kept_geoms.append(centroid)

    deduped = gdf.loc[kept_idx]
    print(f"Deduped ({DEDUP_RADIUS_M}m radius): {len(gdf)} -> {len(deduped)}")

    with open(OUT_PATH, "w") as f:
        for _, row in deduped.iterrows():
            rec = {k: v for k, v in row.items() if k not in ("geometry", "_area")}
            rec["geometry"] = json.loads(gpd.GeoSeries([row.geometry], crs="EPSG:25830").to_crs(epsg=4326).to_json())[
                "features"
            ][0]["geometry"]
            f.write(json.dumps(rec) + "\n")
    print(f"Wrote {OUT_PATH}")
