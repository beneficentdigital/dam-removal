"""Clip the provisional EU-Hydro pull to the real Guadalquivir basin
boundary, buffer, and populate the tile manifest (plan.md stage 0).
"""

import glob
import sys

import geopandas as gpd

sys.path.insert(0, "src")
from scaffold.manifest import add_tile, init_manifest

BOUNDARY_PATH = "data/raw/basin_boundary/guadalquivir_rbd.geojson"
EU_HYDRO_GLOB = "data/raw/eu_hydro/strahler_layer_*.geojson"
BUFFER_METERS = 200
TILE_SIZE_METERS = 5000  # 5km grid cells over the buffered river network
MANIFEST_PATH = "data/manifest/guadalquivir.db"


def main():
    boundary = gpd.read_file(BOUNDARY_PATH)
    print(f"Basin boundary: {len(boundary)} feature(s), CRS {boundary.crs}")

    rivers = gpd.GeoDataFrame(
        gpd.pd.concat([gpd.read_file(p) for p in sorted(glob.glob(EU_HYDRO_GLOB))]),
        crs="EPSG:4326",
    )
    print(f"EU-Hydro pull (provisional bbox): {len(rivers)} features")

    clipped = gpd.clip(rivers, boundary)
    print(f"Clipped to real basin boundary: {len(clipped)} features")
    clipped.to_file("data/processed/eu_hydro_guadalquivir_clipped.gpkg", driver="GPKG")

    # Buffer in a metric CRS (ETRS89 / UTM 30N, EPSG:25830, is standard for
    # peninsular Spain) then union into the AOI.
    clipped_m = clipped.to_crs(epsg=25830)
    aoi = clipped_m.buffer(BUFFER_METERS).union_all()
    aoi_gdf = gpd.GeoDataFrame(geometry=[aoi], crs="EPSG:25830")
    aoi_gdf.to_file("data/processed/aoi_guadalquivir.gpkg", driver="GPKG")
    print(f"AOI (buffered {BUFFER_METERS}m) area: {aoi.area / 1e6:.1f} km2")

    # Tile the AOI's bounding box into a grid, keeping only cells that
    # actually intersect the AOI (most of a bbox grid won't).
    minx, miny, maxx, maxy = aoi.bounds
    init_manifest(MANIFEST_PATH)
    n_tiles = 0
    x = minx
    while x < maxx:
        y = miny
        while y < maxy:
            from shapely.geometry import box

            cell = box(x, y, x + TILE_SIZE_METERS, y + TILE_SIZE_METERS)
            if cell.intersects(aoi):
                tile_id = f"tile_{int((x - minx) // TILE_SIZE_METERS):03d}_{int((y - miny) // TILE_SIZE_METERS):03d}"
                add_tile(MANIFEST_PATH, tile_id, cell.wkt)
                n_tiles += 1
            y += TILE_SIZE_METERS
        x += TILE_SIZE_METERS
    print(f"Manifest populated with {n_tiles} AOI tiles at {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
