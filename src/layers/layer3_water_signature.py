"""Layer 3 -- water-signature detection (plan.md stage 5), NDWI-based.

Computes NDWI (Green/B3 vs NIR/B8) server-side in Earth Engine and
vectorizes the thresholded water mask directly via reduceToVectors --
no raster download needed, unlike Layer 1's RGB tiles. Much faster:
one EE query per tile returns small water-body polygons directly.

Resumable via the manifest's "layer3" column, same pattern as imagery.
"""

import concurrent.futures
import json
import os
import sys

import ee

sys.path.insert(0, "src")
from scaffold.manifest import get_pending_with_geometry, set_status

PROJECT = "sincere-kit-507519-u3"
MANIFEST_PATH = "data/manifest/guadalquivir.db"
OUT_PATH = "data/processed/layer3_water_candidates.jsonl"
DATE_RANGE = ("2023-01-01", "2025-12-31")
CLOUD_MAX_PCT = 20
NDWI_THRESHOLD = 0.2
MIN_AREA_M2 = 200  # drop noise smaller than a ~14x14m speck
TILE_TIMEOUT_S = 90  # earthengine-api has no built-in request timeout --
# a single tile with an unusually complex water mask to vectorize can
# hang indefinitely otherwise (confirmed 2026-09-14: caught a real hang,
# zero progress for a full 10min monitor interval with the process
# still alive, barely any CPU used -- stuck waiting on one EE response)


def init():
    ee.Initialize(project=PROJECT)


def water_polygons_for_tile(geometry_wkt: str) -> list:
    from shapely import wkt as shapely_wkt

    geom = shapely_wkt.loads(geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    region = ee.Geometry.Rectangle([minx, miny, maxx, maxy], proj="EPSG:25830", geodesic=False)

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(*DATE_RANGE)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", CLOUD_MAX_PCT))
    )
    if collection.size().getInfo() == 0:
        return []

    image = collection.median().clip(region)
    ndwi = image.normalizedDifference(["B3", "B8"]).rename("NDWI")
    water_mask = ndwi.gt(NDWI_THRESHOLD).selfMask()

    vectors = water_mask.reduceToVectors(
        geometry=region,
        scale=10,
        crs="EPSG:25830",
        geometryType="polygon",
        eightConnected=True,
        maxPixels=1e9,
    )
    fc = vectors.map(lambda f: f.set("area_m2", f.geometry().area(1))).filter(
        ee.Filter.gt("area_m2", MIN_AREA_M2)
    )
    result = fc.getInfo()
    return result.get("features", [])


if __name__ == "__main__":
    init()
    pending = get_pending_with_geometry(MANIFEST_PATH, "layer3")
    print(f"{len(pending)} tiles pending Layer 3 (water-signature)")

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if limit:
        pending = pending[:limit]
        print(f"Limiting to {limit} tiles")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    n_candidates = 0
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    with open(OUT_PATH, "a") as out_f:
        for tile_id, geometry_wkt in pending:
            try:
                future = executor.submit(water_polygons_for_tile, geometry_wkt)
                features = future.result(timeout=TILE_TIMEOUT_S)
            except concurrent.futures.TimeoutError:
                print(f"  {tile_id}: TIMED OUT after {TILE_TIMEOUT_S}s, skipping")
                set_status(MANIFEST_PATH, tile_id, "layer3", "failed")
                # The hung call keeps running in its own thread, but the
                # main loop moves on rather than blocking indefinitely.
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                continue
            except Exception as e:
                print(f"  {tile_id}: failed ({e})")
                set_status(MANIFEST_PATH, tile_id, "layer3", "failed")
                continue

            for feat in features:
                centroid = feat["geometry"]
                out_f.write(
                    json.dumps({"tile_id": tile_id, "area_m2": feat["properties"]["area_m2"], "geometry": centroid})
                    + "\n"
                )
            n_candidates += len(features)
            set_status(MANIFEST_PATH, tile_id, "layer3", "done")
            print(f"  {tile_id}: {len(features)} water polygons")

    print(f"\nTotal water-body candidates found: {n_candidates}")
