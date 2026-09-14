"""Layer 3 confirmation pass: for each deduped NDWI candidate (fast,
broad, noisy -- layer3_water_signature.py + dedup_ndwi_candidates.py),
pull a small 4-band Sentinel-2 crop and run OmniWaterMask in batches to
confirm/reject it.

Two-stage design (cheap high-recall proposal -> expensive high-precision
confirm) avoids running OmniWaterMask across all 2,369 tiles (~100hrs on
this hardware, confirmed 2026-09-14). Batching + dropping the
building/road OSM checks (we only care about water) cuts per-item cost
further on top of that.

Run under .venv-owm/bin/python3. Crop pulling shells out to the main
Python (3.9, has earthengine-api + auth); this venv doesn't need it.
"""

import concurrent.futures
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANDIDATES_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer3_water_candidates_deduped.jsonl")
CROP_DIR = os.path.join(PROJECT_ROOT, "data/raw/layer3_confirm_crops")
MASK_DIR = os.path.join(PROJECT_ROOT, "data/raw/layer3_confirm_masks")
OUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/layer3_confirmed.jsonl")
BUFFER_M = 150
BATCH_SIZE = 8
PULL_CONCURRENCY = 6


def polygon_centroid(geometry: dict) -> tuple:
    """Returns (lon, lat). Uses shapely rather than manual coordinate
    parsing -- geometry nesting differs between raw Earth Engine
    GeoJSON (Polygon) and the deduped file's shapely-round-tripped
    GeoJSON (can come back as MultiPolygon), which broke a manual
    coords[0] parse here (2026-09-14)."""
    from shapely.geometry import shape

    c = shape(geometry).centroid
    return c.x, c.y


def pull_crop_via_main_python(lon: float, lat: float, out_path: str) -> bool:
    script = f"""
import ee
ee.Initialize(project='sincere-kit-507519-u3')
region = ee.Geometry.Point([{lon},{lat}]).buffer({BUFFER_M}).bounds()
s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(region).filterDate('2023-01-01','2025-12-31').filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
if s2.size().getInfo() == 0:
    print('NO_COVERAGE')
else:
    image = s2.median().clip(region).select(['B4','B3','B2','B8'])
    url = image.getDownloadURL({{'region': region, 'scale': 10, 'crs': 'EPSG:25830', 'format': 'GEO_TIFF'}})
    import urllib.request
    urllib.request.urlretrieve(url, '{out_path}')
    print('OK')
"""
    result = subprocess.run(["python3", "-c", script], capture_output=True, text=True, timeout=60)
    return "OK" in result.stdout


if __name__ == "__main__":
    os.makedirs(CROP_DIR, exist_ok=True)
    os.makedirs(MASK_DIR, exist_ok=True)

    candidates = []
    with open(CANDIDATES_PATH) as f:
        for line in f:
            candidates.append(json.loads(line))
    print(f"{len(candidates)} deduped NDWI candidates to confirm")

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if limit:
        candidates = candidates[:limit]

    # Pull all crops first (concurrently -- I/O-bound, same pattern as
    # pull_imagery.py), so the batched OmniWaterMask call below sees a
    # ready set of local files rather than pulling one-by-one in between
    # inference batches.
    print("Pulling crops...")
    crop_paths = [None] * len(candidates)

    def pull_one(i, cand):
        lon, lat = polygon_centroid(cand["geometry"])
        crop_path = os.path.join(CROP_DIR, f"cand_{i:05d}.tif")
        if os.path.exists(crop_path):
            return i, crop_path, lon, lat
        ok = pull_crop_via_main_python(lon, lat, crop_path)
        return (i, crop_path, lon, lat) if ok else (i, None, lon, lat)

    lonlat = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=PULL_CONCURRENCY) as pool:
        futures = [pool.submit(pull_one, i, c) for i, c in enumerate(candidates)]
        for fut in concurrent.futures.as_completed(futures):
            i, path, lon, lat = fut.result()
            crop_paths[i] = path
            lonlat[i] = (lon, lat)

    valid = [(i, p) for i, p in enumerate(crop_paths) if p is not None]
    print(f"Pulled {len(valid)}/{len(candidates)} crops (rest had no imagery coverage)")

    from omniwatermask import make_water_mask

    confirmed = []
    for batch_start in range(0, len(valid), BATCH_SIZE):
        batch = valid[batch_start : batch_start + BATCH_SIZE]
        batch_paths = [Path(p) for _, p in batch]
        try:
            result_paths = make_water_mask(
                scene_paths=batch_paths,
                band_order=[1, 2, 3, 4],
                batch_size=BATCH_SIZE,
                output_dir=Path(MASK_DIR),
                overwrite=False,
                use_osm_building=False,
                use_osm_roads=False,
            )
        except Exception as e:
            print(f"  batch {batch_start}: failed ({e})")
            continue

        import numpy as np
        import rasterio

        for (i, _), mask_path in zip(batch, result_paths):
            with rasterio.open(mask_path) as src:
                mask = src.read(1)
            water_frac = (mask > 0).mean()
            is_confirmed = water_frac > 0.01
            lon, lat = lonlat[i]
            print(f"  cand_{i:05d}: water_frac={water_frac:.3f} confirmed={is_confirmed}")
            if is_confirmed:
                confirmed.append({**candidates[i], "lon": lon, "lat": lat, "water_frac": float(water_frac)})

    with open(OUT_PATH, "w") as f:
        for c in confirmed:
            f.write(json.dumps(c) + "\n")
    print(f"\nConfirmed {len(confirmed)}/{len(valid)} candidates -> {OUT_PATH}")
