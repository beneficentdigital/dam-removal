"""Dedupe NDWI candidates before the expensive OmniWaterMask confirmation
pass -- the same water body can produce multiple nearby polygons (tile
edges, noisy fragmentation), and confirming each one separately would
waste a meaningful chunk of the ~50s/candidate OmniWaterMask cost.

Also filters to candidates that show ANOMALOUS WIDENING beyond the
river's normal channel -- not merely "touches a river line" (found
2026-09-14, via manual review of real crops: a plain river-touching
test passes every ordinary, un-blocked stretch of river, since a river
trivially touches its own line everywhere. The actual signature of an
impoundment is water that's wider than the channel's normal width at
that point, not just water's presence on the channel at all).
Normal-channel width is scaled by Strahler order (bigger streams are
naturally wider) rather than one fixed width for every stream size.

A separate, real data gap (not a design bug) was also found in the
same review: EU-Hydro maps the Guadalquivir's marshy delta/estuary
near Doñana poorly (127m from the nearest line for a real river reach)
-- that's what constitution.md's Spain-specific hydrography supplement
(IGN's Red Hidrográfica) was meant to fix but was never actually
pulled. Not addressed here; still open.
"""

import json
import os

import geopandas as gpd
from shapely.geometry import shape

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IN_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer3_water_candidates.jsonl")
OUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer3_water_candidates_deduped.jsonl")
RIVERS_PATH = os.path.join(PROJECT_ROOT, "data/processed/eu_hydro_guadalquivir_clipped.gpkg")
DEDUP_RADIUS_M = 50
RIVER_TOLERANCE_M = 30  # for "is this even near a river at all" pre-filter

# Half-width (m) of the "normal channel" per Strahler order -- a
# candidate must extend meaningfully beyond this to count as anomalous
# widening. Rough Mediterranean-basin estimates, not measured.
NORMAL_HALF_WIDTH_BY_STRAHLER = {1: 3, 2: 4, 3: 6, 4: 10, 5: 15, 6: 25, 7: 40, 8: 60, 9: 80}
MIN_EXCESS_AREA_M2 = 400  # ~20x20m of clearly-anomalous pooling
MIN_EXCESS_FRACTION = 0.3  # or 30%+ of the candidate sits outside normal channel


def filter_to_anomalous_widening(gdf_m: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    rivers = gpd.read_file(RIVERS_PATH).to_crs(epsg=25830)
    rivers = rivers[rivers["STRAHLER"].notna()]
    rivers["half_width"] = rivers["STRAHLER"].astype(int).map(NORMAL_HALF_WIDTH_BY_STRAHLER).fillna(10)
    rivers["normal_channel"] = rivers.apply(lambda r: r.geometry.buffer(r["half_width"]), axis=1)
    normal_channel_gdf = gpd.GeoDataFrame(geometry=rivers["normal_channel"], crs=rivers.crs)

    # Pre-filter: must be within reach of a river at all (cheap, avoids
    # doing the expensive difference() on obviously-unrelated candidates).
    rivers_wide = rivers.copy()
    rivers_wide["geometry"] = rivers.geometry.buffer(RIVER_TOLERANCE_M)
    joined = gpd.sjoin(gdf_m, rivers_wide[["geometry"]], how="left", predicate="intersects")
    near_river = joined.groupby(joined.index)["index_right"].apply(lambda x: x.notna().any())
    candidates = gdf_m[near_river.reindex(gdf_m.index, fill_value=False)].copy()

    # For each surviving candidate, subtract the normal-channel buffer of
    # every nearby river segment and check how much area is left over.
    normal_union = normal_channel_gdf.geometry.union_all()
    keep_idx = []
    for idx, row in candidates.iterrows():
        excess = row.geometry.difference(normal_union)
        excess_area = excess.area
        total_area = row.geometry.area
        if excess_area > MIN_EXCESS_AREA_M2 and (total_area == 0 or excess_area / total_area > MIN_EXCESS_FRACTION):
            keep_idx.append(idx)
    return candidates.loc[keep_idx]


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

    gdf = filter_to_anomalous_widening(gdf)
    print(f"Filtered to anomalous widening (excess >{MIN_EXCESS_AREA_M2}m2 and >{MIN_EXCESS_FRACTION:.0%}): {len(records)} -> {len(gdf)}")

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
