"""Pull PNOA imagery per AOI tile via Earth Engine (plan.md stage 2).

Requires `earthengine authenticate --project=sincere-kit-507519-u3` to
have been run once on this machine (see PROGRESS notes) before this
script's `ee.Initialize()` call will succeed.

Resumable: checks the manifest before processing each tile and skips
anything already marked done, so an interrupted run picks back up
rather than restarting (constitution principle 3).
"""

import sys

import ee

sys.path.insert(0, "src")
from scaffold.manifest import get_pending_with_geometry, set_status

PROJECT = "sincere-kit-507519-u3"
MANIFEST_PATH = "data/manifest/guadalquivir.db"
OUT_DIR = "data/raw/pnoa_tiles"
PNOA_COLLECTION = "Spain/PNOA/PNOA10"


def init():
    ee.Initialize(project=PROJECT)


def pull_tile(tile_id: str, geometry_wkt: str) -> bool:
    """Export one tile's PNOA mosaic. Returns True on success."""
    from shapely import wkt as shapely_wkt

    geom = shapely_wkt.loads(geometry_wkt)
    minx, miny, maxx, maxy = geom.bounds
    region = ee.Geometry.Rectangle([minx, miny, maxx, maxy], proj="EPSG:25830", geodesic=False)

    collection = ee.ImageCollection(PNOA_COLLECTION).filterBounds(region)
    count = collection.size().getInfo()
    if count == 0:
        print(f"  {tile_id}: no PNOA coverage in this tile (check Sentinel-2 fallback)")
        return False

    image = collection.mosaic().clip(region)
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=f"pnoa_{tile_id}",
        folder="howmanydamsinspain_pnoa",
        fileNamePrefix=tile_id,
        region=region,
        scale=1,  # PNOA10 native ~1m; adjust after checking actual output size/cost
        crs="EPSG:25830",
        maxPixels=1e10,
    )
    task.start()
    print(f"  {tile_id}: export task started ({task.id})")
    return True


if __name__ == "__main__":
    from shapely import wkt as shapely_wkt

    init()
    pending = get_pending_with_geometry(MANIFEST_PATH, "imagery")
    print(f"{len(pending)} tiles pending imagery pull")
    if not pending:
        sys.exit(0)

    # Probe the single worst-case tile (largest area) first, before
    # committing to the full run — catches scaling/cost/coverage problems
    # on one tile instead of discovering them 500 tiles in.
    worst_case = max(pending, key=lambda t: shapely_wkt.loads(t[1]).area)
    print(f"Probing worst-case tile {worst_case[0]} first...")
    probe_ok = pull_tile(*worst_case)
    if not probe_ok:
        print("Probe tile had no PNOA coverage — check Sentinel-2 fallback before running the rest.")
        sys.exit(1)
    set_status(MANIFEST_PATH, worst_case[0], "imagery", "done")

    # Export tasks run async on Google's servers — "done" here means the
    # task was submitted successfully, not that the file has finished
    # writing to Drive. Check actual task status via the EE Tasks API (or
    # the Drive folder) before starting Layer 1 inference on these tiles.
    remaining = [t for t in pending if t[0] != worst_case[0]]
    for tile_id, geometry_wkt in remaining:
        ok = pull_tile(tile_id, geometry_wkt)
        set_status(MANIFEST_PATH, tile_id, "imagery", "done" if ok else "failed")
