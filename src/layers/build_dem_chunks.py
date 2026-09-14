"""Define DEM analysis chunks for Layer 2 -- large contiguous areas
(unlike the 5km imagery tile grid), since flow accumulation needs real
upstream watershed area to be meaningful (see research-brief.md finding,
2026-09-14: 5km tiles in isolation topped out at flow-accumulation=36,
useless for stream detection).

Each chunk is a 40km "core" plus a 5km buffer on every side (fetched at
25m resolution -- still resolves check-dam-scale features, keeps each
raster ~2000x2000px). Step-anomaly candidates are only kept if they fall
within a chunk's core, so overlapping buffers don't produce duplicates.
"""

import json
import os

import geopandas as gpd
from shapely.geometry import box

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOUNDARY_PATH = os.path.join(PROJECT_ROOT, "data/raw/basin_boundary/guadalquivir_rbd.geojson")
OUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/dem_chunks.json")

CORE_SIZE_M = 40000
BUFFER_M = 5000

if __name__ == "__main__":
    boundary = gpd.read_file(BOUNDARY_PATH).to_crs(epsg=25830)
    minx, miny, maxx, maxy = boundary.total_bounds

    chunks = []
    y = miny
    row = 0
    while y < maxy:
        x = minx
        col = 0
        while x < maxx:
            core = box(x, y, x + CORE_SIZE_M, y + CORE_SIZE_M)
            if core.intersects(boundary.union_all()):
                fetch = box(x - BUFFER_M, y - BUFFER_M, x + CORE_SIZE_M + BUFFER_M, y + CORE_SIZE_M + BUFFER_M)
                chunks.append(
                    {
                        "chunk_id": f"dem_chunk_{row:02d}_{col:02d}",
                        "core_bounds": [x, y, x + CORE_SIZE_M, y + CORE_SIZE_M],
                        "fetch_bounds": list(fetch.bounds),
                        "status": "pending",
                    }
                )
            x += CORE_SIZE_M
            col += 1
        y += CORE_SIZE_M
        row += 1

    with open(OUT_PATH, "w") as f:
        json.dump(chunks, f, indent=2)
    print(f"Defined {len(chunks)} DEM chunks (40km core + 5km buffer, 25m resolution) -> {OUT_PATH}")
