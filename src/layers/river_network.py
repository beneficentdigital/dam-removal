"""Shared combined river network (EU-Hydro + Red Hidrografica), used by
both the Layer 3 anomalous-widening filter (dedup_ndwi_candidates.py)
and the fusion canonical-point rule (plan.md: "every layer reduces its
output to the same kind of point before fusion -- where the detected
structure/impoundment crosses the river centerline, not a bounding-box
or blob centroid").
"""

import os

import geopandas as gpd
from shapely import STRtree
from shapely.geometry import Point

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EU_HYDRO_PATH = os.path.join(PROJECT_ROOT, "data/processed/eu_hydro_guadalquivir_clipped.gpkg")
RED_HIDRO_PATH = os.path.join(PROJECT_ROOT, "data/raw/red_hidrografica_watercourses.gpkg")

_cache = {}


def load_combined_rivers_m() -> gpd.GeoDataFrame:
    """Both networks, reprojected to EPSG:25830 (meters) and combined --
    no attribute alignment needed since callers here only use geometry."""
    if "rivers" not in _cache:
        eu_hydro = gpd.read_file(EU_HYDRO_PATH).to_crs(epsg=25830)
        red_hidro = gpd.read_file(RED_HIDRO_PATH).to_crs(epsg=25830)
        _cache["rivers"] = gpd.GeoDataFrame(
            geometry=list(eu_hydro.geometry) + list(red_hidro.geometry), crs="EPSG:25830"
        )
    return _cache["rivers"]


def _river_tree() -> STRtree:
    if "tree" not in _cache:
        _cache["tree"] = STRtree(load_combined_rivers_m().geometry.values)
    return _cache["tree"]


def snap_to_nearest_river_point(lon: float, lat: float) -> tuple:
    """Returns (lon, lat) of the nearest point on the combined river
    network to the given point -- the canonical-point rule above."""
    pt_m = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(epsg=25830).iloc[0]
    nearest_idx = _river_tree().nearest(pt_m)
    nearest_line = load_combined_rivers_m().geometry.iloc[nearest_idx]
    snapped_m = nearest_line.interpolate(nearest_line.project(pt_m))
    snapped_4326 = gpd.GeoSeries([snapped_m], crs="EPSG:25830").to_crs(epsg=4326).iloc[0]
    return snapped_4326.x, snapped_4326.y
