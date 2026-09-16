"""Pull full PNOA coverage (not just point-crops) over a small pilot
sub-area of the river corridor, at native 0.5m/px resolution -- a real
test of Layer 1's basin-wide inference before committing disk/time to
the full 115-187GB basin-wide pull (see tasks.md T022).

Pilot area: a 0.1deg (~10km) cell around the densest known-dam cluster
in the ground truth (36.85-36.95N, -3.95 to -3.85E), chosen so real
detections have real ground truth nearby to compare against.
"""

import os

import geopandas as gpd
import pyproj
import requests
from shapely.geometry import box

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(PROJECT_ROOT, "data/raw/pnoa_pilot_area")
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "data/processed/pnoa_pilot_tiles.gpkg")

WMS_URL = "https://www.ign.es/wms-inspire/pnoa-ma"
LAYER = "OI.OrthoimageCoverage"
CRS = "EPSG:25830"
RES_M = 0.5  # native PNOA resolution
TILE_M = 500  # -> 1000x1000px per request, a safe WMS size
PIXELS = int(TILE_M / RES_M)

PILOT_BBOX_WGS84 = (-3.95, 36.85, -3.85, 36.95)  # lon0, lat0, lon1, lat1
BUFFER_M = 200  # river corridor half-width, same convention as the rest of the pipeline


def build_pilot_tiles() -> gpd.GeoDataFrame:
    import sys

    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src/layers"))
    from river_network import load_combined_rivers_m

    transformer = pyproj.Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    x0, y0 = transformer.transform(PILOT_BBOX_WGS84[0], PILOT_BBOX_WGS84[1])
    x1, y1 = transformer.transform(PILOT_BBOX_WGS84[2], PILOT_BBOX_WGS84[3])

    rivers = load_combined_rivers_m()
    clipped = rivers.geometry.clip(box(x0, y0, x1, y1))
    clipped = clipped[~clipped.is_empty]
    corridor = clipped.buffer(BUFFER_M).union_all()

    tiles = []
    tx0 = int(x0 // TILE_M) * TILE_M
    ty0 = int(y0 // TILE_M) * TILE_M
    x = tx0
    while x < x1:
        y = ty0
        while y < y1:
            tile_box = box(x, y, x + TILE_M, y + TILE_M)
            if corridor.intersects(tile_box):
                tiles.append({"tile_id": f"pnoa_pilot_{int(x)}_{int(y)}", "geometry": tile_box})
            y += TILE_M
        x += TILE_M

    gdf = gpd.GeoDataFrame(tiles, crs=CRS)
    gdf.to_file(MANIFEST_PATH, driver="GPKG")
    print(f"{len(gdf)} tiles needed to cover the pilot corridor -> {MANIFEST_PATH}")
    return gdf


def fetch_tile(minx, miny, maxx, maxy, out_path: str) -> bool:
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": LAYER,
        "STYLES": "",
        "CRS": CRS,
        "BBOX": f"{minx},{miny},{maxx},{maxy}",
        "WIDTH": PIXELS,
        "HEIGHT": PIXELS,
        "FORMAT": "image/png",
    }
    resp = requests.get(WMS_URL, params=params, timeout=60)
    resp.raise_for_status()
    if resp.headers.get("content-type", "").startswith("image"):
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return True
    print(f"  unexpected response for {out_path}: {resp.headers.get('content-type')}")
    return False


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    tiles = build_pilot_tiles()

    n_ok = 0
    for _, row in tiles.iterrows():
        out_path = os.path.join(OUT_DIR, f"{row['tile_id']}.png")
        if os.path.exists(out_path):
            n_ok += 1
            continue
        minx, miny, maxx, maxy = row.geometry.bounds
        try:
            ok = fetch_tile(minx, miny, maxx, maxy, out_path)
            n_ok += ok
        except Exception as e:
            print(f"  failed for {row['tile_id']}: {e}")

    print(f"Done: {n_ok}/{len(tiles)} tiles saved to {OUT_DIR}/")
