"""Generate the pilot's shareable deliverables (plan.md stage 10):
pilot_output.csv (every fused candidate) and review_uncertain.csv (the
new-uncertain subset, each with an Earth Engine thumbnail URL so it can
be reviewed without GEE/Colab access, per FR-013).

Run after src/fusion/fuse_candidates.py.
"""

import os
import subprocess
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FUSED_PATH = os.path.join(PROJECT_ROOT, "data/processed/fused_candidates.csv")
PILOT_OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/pilot_output.csv")
REVIEW_UNCERTAIN_PATH = os.path.join(PROJECT_ROOT, "data/processed/review_uncertain.csv")
THUMB_BUFFER_M = 400  # wide enough to show riverbank/land context around the water, not just a mostly-water
# crop -- a tight buffer (150m, matched to the Layer 3 confirm crop) is fine for a model decision but gives a
# human reviewer almost nothing to visually judge "is this a dam" against (found 2026-09-15)

# FR-008's minimum columns, plus the provenance fields constitution.md
# principle 5 requires (which layer(s), confidence, matched source).
PILOT_OUTPUT_COLUMNS = [
    "lat",
    "lon",
    "layers",
    "n_layers",
    "confidence",
    "per_layer_confidence",
    "match_status",
    "matched_source",
    "matched_source_id",
    "matched_distance_m",
    "source_refs",
]


def get_thumbnail_url(lon: float, lat: float) -> str:
    """Shells out to the main (EE-authenticated) Python, same pattern as
    layer3_confirm_owm.py's crop pulling -- this venv doesn't carry
    earthengine-api/auth. getThumbURL() returns a URL that's viewable by
    anyone with the link, no GEE account needed on the viewer's end."""
    script = f"""
import ee
ee.Initialize(project='sincere-kit-507519-u3')
region = ee.Geometry.Point([{lon},{lat}]).buffer({THUMB_BUFFER_M}).bounds()
s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(region).filterDate('2023-01-01','2025-12-31').filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
image = s2.median().clip(region).select(['B4','B3','B2'])
# A fixed min/max (the usual S2 true-color preset, ~0-3000) rendered
# near-black here -- this AOI's actual reflectance percentiles turned
# out to be ~150-400, nowhere near that preset's assumed range (found
# 2026-09-15 probing a real candidate). Stretch to each thumbnail's own
# 2nd-98th percentile instead of a fixed range so it self-calibrates.
stats = image.reduceRegion(ee.Reducer.percentile([2, 98]), region, 10).getInfo()
# Per-band, not one shared min/max across all three -- Sentinel-2's
# green band (B3) runs meaningfully hotter than red/blue in vegetated
# scenes, so a shared range blew everything out to a green wash (found
# 2026-09-15, same probe as the min/max-range fix above).
bands = ['B4', 'B3', 'B2']
mins = [stats[b + '_p2'] for b in bands]
maxs = [stats[b + '_p98'] for b in bands]
url = image.getThumbURL({{'region': region, 'dimensions': 512, 'format': 'png', 'min': mins, 'max': maxs}})
print(url)
"""
    result = subprocess.run(["python3", "-c", script], capture_output=True, text=True, timeout=60)
    url = result.stdout.strip()
    return url if url.startswith("http") else ""


def run(skip_thumbnails: bool = False):
    if not os.path.exists(FUSED_PATH):
        print(f"No fused candidates at {FUSED_PATH} -- run src/fusion/fuse_candidates.py first")
        sys.exit(1)

    fused = pd.read_csv(FUSED_PATH)

    pilot_output = fused.reindex(columns=PILOT_OUTPUT_COLUMNS)
    pilot_output.to_csv(PILOT_OUTPUT_PATH, index=False)
    print(f"Wrote {len(pilot_output)} rows -> {PILOT_OUTPUT_PATH}")
    print(pilot_output["match_status"].value_counts())

    review = fused[fused["match_status"] == "new-uncertain"].copy()
    if skip_thumbnails:
        review["ee_thumbnail_url"] = ""
    else:
        print(f"Generating {len(review)} thumbnail URLs...")
        review["ee_thumbnail_url"] = [get_thumbnail_url(row["lon"], row["lat"]) for _, row in review.iterrows()]
        n_failed = (review["ee_thumbnail_url"] == "").sum()
        if n_failed:
            print(f"  {n_failed}/{len(review)} thumbnail URLs failed to generate")

    review = review.reindex(columns=PILOT_OUTPUT_COLUMNS + ["ee_thumbnail_url"])
    review.to_csv(REVIEW_UNCERTAIN_PATH, index=False)
    print(f"Wrote {len(review)} rows -> {REVIEW_UNCERTAIN_PATH}")


if __name__ == "__main__":
    run(skip_thumbnails="--skip-thumbnails" in sys.argv)
