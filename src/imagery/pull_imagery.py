"""Pull imagery per AOI tile via Earth Engine (plan.md stage 2).

PNOA10 (Spain/PNOA/PNOA10) was confirmed NOT to cover the Guadalquivir
basin at all -- its entire collection extent is roughly lat 38.6-43.4
(northern/central Spain), while Guadalquivir sits at 36.7-38.7. So this
pilot uses Sentinel-2 as the PRIMARY imagery source, not a fallback, per
FR-002's documented fallback path. Direct per-tile download (getDownloadURL)
is used instead of Drive export -- tiles are small enough (5km, ~500x500px
at 10m) to fetch synchronously, and this avoids needing separate Google
Drive API credentials on top of Earth Engine auth.

Requires `earthengine --project=sincere-kit-507519-u3 authenticate` to
have been run once on this machine before ee.Initialize() will succeed.

Resumable: checks the manifest before processing each tile and skips
anything already marked done (constitution principle 3).
"""

import concurrent.futures
import os
import sys
import time
import urllib.request

import ee
from shapely import wkt as shapely_wkt

sys.path.insert(0, "src")
from scaffold.manifest import get_pending_with_geometry, set_status

PROJECT = "sincere-kit-507519-u3"
MANIFEST_PATH = "data/manifest/guadalquivir.db"
OUT_DIR = "data/raw/sentinel2_tiles"
SCALE_M = 10  # Sentinel-2 native resolution for the RGB bands used
DATE_RANGE = ("2023-01-01", "2025-12-31")  # widen if a tile has poor S2 coverage
CLOUD_MAX_PCT = 20
MAX_RETRIES = 3
CONCURRENCY = int(os.environ.get("PULL_CONCURRENCY", 10))  # I/O-bound, not CPU-bound


def init():
    ee.Initialize(project=PROJECT)


def pull_tile(tile_id: str, geometry_wkt: str) -> bool:
    """Download one tile's cloud-filtered Sentinel-2 median composite.
    Returns True on success (including 'no imagery found', which is
    marked failed by the caller for manual follow-up)."""
    geom = shapely_wkt.loads(geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    region = ee.Geometry.Rectangle([minx, miny, maxx, maxy], proj="EPSG:25830", geodesic=False)

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(*DATE_RANGE)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", CLOUD_MAX_PCT))
    )
    count = collection.size().getInfo()
    if count == 0:
        print(f"  {tile_id}: no Sentinel-2 imagery in range/cloud threshold")
        return False

    image = collection.median().clip(region).select(["B4", "B3", "B2"])
    url = image.getDownloadURL(
        {"region": region, "scale": SCALE_M, "crs": "EPSG:25830", "format": "GEO_TIFF"}
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = f"{OUT_DIR}/{tile_id}.tif"
    urllib.request.urlretrieve(url, out_path)
    size = os.path.getsize(out_path)
    print(f"  {tile_id}: {count} source images -> {size} bytes")
    return True


def pull_tile_safe(tile_id: str, geometry_wkt: str) -> tuple[str, bool]:
    """Wraps pull_tile with retries so one flaky network call (a real
    TimeoutError killed an earlier unguarded run) can't take down a
    multi-hour batch. Any failure after retries is marked, not raised."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return tile_id, pull_tile(tile_id, geometry_wkt)
        except Exception as e:
            print(f"  {tile_id}: attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
    return tile_id, False


if __name__ == "__main__":
    init()
    pending = get_pending_with_geometry(MANIFEST_PATH, "imagery")
    print(f"{len(pending)} tiles pending imagery pull")
    if not pending:
        sys.exit(0)

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if limit:
        print(f"Limiting this run to {limit} tiles (pass no argument for the full run)")
        pending = pending[:limit]

    # Probe the worst-case tile (largest area) first, serially, before
    # spawning concurrent workers for the rest.
    worst_case = max(pending, key=lambda t: shapely_wkt.loads(t[1]).area)
    print(f"Probing worst-case tile {worst_case[0]} first...")
    _, probe_ok = pull_tile_safe(*worst_case)
    set_status(MANIFEST_PATH, worst_case[0], "imagery", "done" if probe_ok else "failed")
    if not probe_ok:
        print("Probe tile failed -- stopping before the full run so this can be investigated.")
        sys.exit(1)

    remaining = [t for t in pending if t[0] != worst_case[0]]
    print(f"Pulling remaining {len(remaining)} tiles with {CONCURRENCY} concurrent workers...")
    n_done = n_failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(pull_tile_safe, tid, geom): tid for tid, geom in remaining}
        for future in concurrent.futures.as_completed(futures):
            tile_id, ok = future.result()
            set_status(MANIFEST_PATH, tile_id, "imagery", "done" if ok else "failed")
            n_done += ok
            n_failed += not ok
            if (n_done + n_failed) % 20 == 0:
                print(f"  progress: {n_done} done, {n_failed} failed, "
                      f"{len(remaining) - n_done - n_failed} remaining")

    print(f"Finished: {n_done} done, {n_failed} failed out of {len(remaining)}")
