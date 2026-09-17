"""Pull IGN's hy-p:DamOrWeir layer (same WFS as Red Hidrografica's
watercourses, servicios.idee.es/wfs-inspire/hidrografia) -- a 5th
ground-truth source found 2026-09-14 but never pulled or merged
(28,774 features nationally). CC BY 4.0, same terms as the
watercourses layer pulled from this WFS already.

Each feature is a short LineString marking the dam/weir across the
channel, not a point -- we record its centroid as lat/lon to match
the other ground-truth sources' schema.
"""

import os

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WFS_URL = "https://servicios.idee.es/wfs-inspire/hidrografia"
TYPENAME = "hy-p:DamOrWeir"
BASIN_PATH = os.path.join(PROJECT_ROOT, "data/raw/basin_boundary/guadalquivir_rbd.geojson")
OUT_PATH = os.path.join(PROJECT_ROOT, "data/raw/dam_or_weir.gpkg")
PAGE_SIZE = 1000
SAFETY_CAP = 100  # pages -- 100k features, well above the 28,774 national total


def fetch_all_features() -> gpd.GeoDataFrame:
    basin = gpd.read_file(BASIN_PATH).to_crs(epsg=4258)  # ETRS89, matches the WFS's native CRS
    minx, miny, maxx, maxy = basin.total_bounds

    all_gdfs = []
    start_index = 0
    for page in range(SAFETY_CAP):
        url = (
            f"{WFS_URL}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature"
            f"&TYPENAMES={TYPENAME}&COUNT={PAGE_SIZE}&STARTINDEX={start_index}"
            f"&BBOX={miny},{minx},{maxy},{maxx},urn:ogc:def:crs:EPSG::4258"
        )
        gdf = gpd.read_file(url)
        print(f"  page {page}: {len(gdf)} features (startIndex={start_index})")
        if len(gdf) == 0:
            break
        all_gdfs.append(gdf)
        if len(gdf) < PAGE_SIZE:
            break
        start_index += PAGE_SIZE
    else:
        print(f"  WARNING: hit the {SAFETY_CAP}-page safety cap, results may be incomplete")

    combined = pd.concat(all_gdfs, ignore_index=True)
    return gpd.GeoDataFrame(combined, crs="EPSG:4258")


if __name__ == "__main__":
    gdf = fetch_all_features()
    print(f"{len(gdf)} DamOrWeir features pulled for the basin bbox")

    basin = gpd.read_file(BASIN_PATH).to_crs(epsg=4258)
    centroids_m = gdf.geometry.to_crs(epsg=25830).centroid.to_crs(epsg=4258)
    clipped = gdf[centroids_m.within(basin.union_all())]
    print(f"{len(clipped)} after clipping to the real basin polygon")

    clipped = clipped.to_crs(epsg=4326)
    clipped.to_file(OUT_PATH, driver="GPKG")
    print(f"Wrote {OUT_PATH}")
