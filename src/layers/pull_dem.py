"""Pull PNOA-MDT elevation data per AOI tile via IGN's public WCS 2.0
service (no auth needed) -- foundation for Layer 2 (DEM/hydrological),
plan.md stage 4. Blind reproduction of Dai et al.'s method, since no
reply has come from the outreach email yet (constitution.md).
"""

import concurrent.futures
import os
import sys
import time

import requests

sys.path.insert(0, "src")
from scaffold.manifest import get_pending_with_geometry, set_status

WCS_URL = "https://servicios.idee.es/wcs-inspire/mdt"
COVERAGE_ID = "Elevacion25830_5"  # 5m resolution, EPSG:25830
MANIFEST_PATH = "data/manifest/guadalquivir.db"
OUT_DIR = "data/raw/dem_tiles"
MAX_RETRIES = 3
CONCURRENCY = int(os.environ.get("PULL_CONCURRENCY", 8))


def fetch_dem_tile(tile_id: str, geometry_wkt: str) -> bool:
    from shapely import wkt as shapely_wkt

    geom = shapely_wkt.loads(geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    params = {
        "SERVICE": "WCS",
        "VERSION": "2.0.1",
        "REQUEST": "GetCoverage",
        "COVERAGEID": COVERAGE_ID,
        "SUBSET": [f"x({minx},{maxx})", f"y({miny},{maxy})"],
        "FORMAT": "image/tiff",
    }
    resp = requests.get(WCS_URL, params=params, timeout=60)
    resp.raise_for_status()
    if b"Exception" in resp.content[:500]:
        return False
    out_path = os.path.join(OUT_DIR, f"{tile_id}.tif")
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return True


def fetch_dem_tile_safe(tile_id: str, geometry_wkt: str) -> tuple:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return tile_id, fetch_dem_tile(tile_id, geometry_wkt)
        except Exception as e:
            print(f"  {tile_id}: attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
    return tile_id, False


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    pending = get_pending_with_geometry(MANIFEST_PATH, "layer2")
    print(f"{len(pending)} tiles pending DEM pull")

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if limit:
        pending = pending[:limit]
        print(f"Limiting to {limit} tiles")

    n_done = n_failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(fetch_dem_tile_safe, tid, geom): tid for tid, geom in pending}
        for future in concurrent.futures.as_completed(futures):
            tile_id, ok = future.result()
            set_status(MANIFEST_PATH, tile_id, "layer2", "done" if ok else "failed")
            n_done += ok
            n_failed += not ok
            if (n_done + n_failed) % 50 == 0:
                print(f"  progress: {n_done} done, {n_failed} failed")

    print(f"Finished: {n_done} done, {n_failed} failed out of {len(pending)}")
