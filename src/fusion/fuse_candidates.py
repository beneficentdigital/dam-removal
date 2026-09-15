"""Fuse per-layer barrier candidates into one record per physical
structure (plan.md stage 7, FR-006), match against ground truth (stage
8, FR-005 via match_ground_truth.py), and apply the confirmed/uncertain
rule (stage 9, FR-005a).

Only Layer 3 has real per-candidate confidence data right now -- Layer 1
isn't trained, Layer 2 is stopped (constitution.md fallback), and Layer
4 only confirms candidates other layers already found rather than
proposing its own (constitution.md, T032), so it isn't a fusion input.
The fusion engine itself is written against however many layers are
registered in LAYER_NORMALIZERS, so adding Layer 1 later is a matter of
adding one normalizer function, not rewriting the merge/classify logic.
"""

import json
import os
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "layers"))
from match_ground_truth import match_candidates  # noqa: E402
from river_network import snap_to_nearest_river_point  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/fused_candidates.csv")

FUSION_RADIUS_M = 50  # locked, plan.md stage 7
CONFIRMED_CONFIDENCE_THRESHOLD = 0.85  # plan.md stage 9 starting point, FR-005a


def normalize_layer3(path=None):
    """layer3_confirm_owm.py's output: one row per OmniWaterMask-confirmed
    NDWI candidate. water_frac (fraction of the crop OWM calls water) is
    the confidence proxy -- not calibrated against ground truth yet, so
    treat the 0.85 threshold below as provisional for this layer too."""
    path = path or os.path.join(PROJECT_ROOT, "data/processed/layer3_confirmed.jsonl")
    records = []
    if not os.path.exists(path):
        return records
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            centroid = shape(rec["geometry"]).centroid
            raw_lon, raw_lat = rec.get("lon", centroid.x), rec.get("lat", centroid.y)
            # Canonical point rule (plan.md): reduce to where the
            # impoundment crosses the river centerline, not the raw
            # blob centroid -- for a large reservoir polygon those can
            # be hundreds of meters apart, which was silently failing
            # every ground-truth match (found 2026-09-15: 0/28 matched
            # before this fix, since SNCZI/AMBER/etc. register the dam
            # structure's point, not the reservoir's center of mass).
            lon, lat = snap_to_nearest_river_point(raw_lon, raw_lat)
            records.append(
                {
                    "layer": "layer3_water_signature",
                    "lat": lat,
                    "lon": lon,
                    "confidence": rec["water_frac"],
                    "source_ref": rec["tile_id"],
                }
            )
    return records


LAYER_NORMALIZERS = {
    "layer3_water_signature": normalize_layer3,
}


def load_all_candidates():
    all_records, available = [], []
    for name, normalizer in LAYER_NORMALIZERS.items():
        records = normalizer()
        if records:
            available.append(name)
        all_records.extend(records)
    return all_records, available


def fuse(records: list) -> pd.DataFrame:
    """Greedy single-linkage clustering within FUSION_RADIUS_M: any two
    candidates within the radius (same or different layer) end up in one
    fused record, transitively (A-B and B-C within radius fuses A/B/C
    even if A-C alone wouldn't qualify) via union-find. Candidate counts
    here are small (hundreds, not millions) so an O(n log n) spatial-index
    neighbor query per point is cheap -- no need for DBSCAN or similar."""
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=["lat", "lon", "layers", "confidence", "n_layers", "source_refs"])

    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326").to_crs(epsg=25830)

    n = len(gdf)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    sindex = gdf.sindex
    for i, geom in enumerate(gdf.geometry):
        for j in sindex.query(geom.buffer(FUSION_RADIUS_M), predicate="intersects"):
            if j != i:
                union(i, int(j))

    gdf["_cluster"] = [find(i) for i in range(n)]

    fused_rows = []
    for _, group in gdf.groupby("_cluster"):
        centroid_4326 = gpd.GeoSeries([group.geometry.union_all().centroid], crs=group.crs).to_crs(epsg=4326).iloc[0]
        layers = sorted(group["layer"].unique().tolist())
        per_layer_confidence = group.groupby("layer")["confidence"].max().round(4).to_dict()
        fused_rows.append(
            {
                "lat": centroid_4326.y,
                "lon": centroid_4326.x,
                "layers": ";".join(layers),
                "n_layers": len(layers),
                "confidence": max(per_layer_confidence.values()),
                "per_layer_confidence": json.dumps(per_layer_confidence),
                "source_refs": ";".join(sorted(group["source_ref"].astype(str).unique())),
            }
        )
    return pd.DataFrame(fused_rows)


def classify(row) -> str:
    """FR-005a: unmatched candidates only reach here (known is decided by
    the ground-truth join first). new-confirmed needs either 2+
    independent layers agreeing within the fusion radius, or a single
    layer at high confidence; everything else is new-uncertain, never
    silently dropped or promoted (constitution.md human-review-tier
    decision)."""
    if row["n_layers"] >= 2 or row["confidence"] >= CONFIRMED_CONFIDENCE_THRESHOLD:
        return "new-confirmed"
    return "new-uncertain"


def run() -> pd.DataFrame:
    records, available_layers = load_all_candidates()
    print(f"Loaded {len(records)} raw candidates from layers: {available_layers or '(none)'}")

    fused = fuse(records)
    print(f"Fused into {len(fused)} candidate structures (<= {FUSION_RADIUS_M}m radius)")

    if fused.empty:
        fused["match_status"] = []
        return fused

    fused_gdf = gpd.GeoDataFrame(fused, geometry=gpd.points_from_xy(fused["lon"], fused["lat"]), crs="EPSG:4326")
    matched = match_candidates(fused_gdf)
    print(matched["match_status"].value_counts())

    unmatched = matched["match_status"] == "new"
    matched.loc[unmatched, "match_status"] = matched.loc[unmatched].apply(classify, axis=1)
    print("After confirmed/uncertain rule:")
    print(matched["match_status"].value_counts())
    return matched


if __name__ == "__main__":
    result = run()
    result.to_csv(OUT_PATH, index=False)
    print(f"Wrote {OUT_PATH}")
