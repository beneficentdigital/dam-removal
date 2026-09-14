"""Merge the 55 DEM chunks (pull_dem_chunks.py) into one whole-basin
contiguous raster. Required because flow accumulation needs the real
upstream watershed in one array -- confirmed twice (2026-09-14) that
any chunking, even 50km chunks, badly undercounts contributing area for
anything but the smallest local streams.
"""

import glob
import os

import rasterio
from rasterio.merge import merge

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHUNK_DIR = os.path.join(PROJECT_ROOT, "data/raw/dem_chunks")
OUT_PATH = os.path.join(PROJECT_ROOT, "data/processed/dem_basin_mosaic.tif")

if __name__ == "__main__":
    files = sorted(glob.glob(f"{CHUNK_DIR}/*.tif"))
    print(f"Merging {len(files)} DEM chunks...")

    sources = [rasterio.open(f) for f in files]
    mosaic, out_transform = merge(sources, method="first")
    print(f"Mosaic shape: {mosaic.shape} ({mosaic.nbytes / 1e9:.2f} GB in memory)")

    out_meta = sources[0].meta.copy()
    out_meta.update(
        {
            "height": mosaic.shape[1],
            "width": mosaic.shape[2],
            "transform": out_transform,
        }
    )
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with rasterio.open(OUT_PATH, "w", **out_meta) as dest:
        dest.write(mosaic)

    for s in sources:
        s.close()
    print(f"Wrote {OUT_PATH}")
