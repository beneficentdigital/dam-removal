"""Run the fine-tuned Layer 1 YOLOv8n model across the PNOA pilot-area
tiles (pull_pnoa_pilot_area.py), project each detection onto the
nearest river-line point (canonical point rule), dedup within 50m
(matching the fusion radius), and match against ground truth -- a real
test of whether basin-wide Layer 1 inference is worth the full pull
(tasks.md T022).
"""

import os
import sys

import geopandas as gpd
import pandas as pd
import pyproj
from ultralytics import YOLO

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src/layers"))
from river_network import snap_to_nearest_river_point  # noqa: E402

TILES_DIR = os.path.join(PROJECT_ROOT, "data/raw/pnoa_pilot_area")
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "data/processed/pnoa_pilot_tiles.gpkg")
MODEL_PATH = os.path.join(PROJECT_ROOT, "data/processed/yolo_dataset_full/run/weights/best.pt")
OUT_CSV = os.path.join(PROJECT_ROOT, "data/processed/layer1_pilot_detections.csv")
CRS = "EPSG:25830"
TILE_M = 500
CONF_THRESHOLD = 0.25
DEDUP_RADIUS_M = 50

_transformer = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)


def run_inference():
    tiles = gpd.read_file(MANIFEST_PATH)
    model = YOLO(MODEL_PATH)

    raw_detections = []
    for _, row in tiles.iterrows():
        tile_path = os.path.join(TILES_DIR, f"{row['tile_id']}.png")
        if not os.path.exists(tile_path):
            continue
        minx, miny, maxx, maxy = row.geometry.bounds
        try:
            results = model.predict(tile_path, conf=CONF_THRESHOLD, verbose=False)
        except Exception as e:
            print(f"  skipping unreadable tile {row['tile_id']}: {e}")
            continue
        if not results:
            continue
        boxes = results[0].boxes
        if len(boxes) == 0:
            continue
        img_w, img_h = results[0].orig_shape[1], results[0].orig_shape[0]
        for box, conf in zip(boxes.xyxy.tolist(), boxes.conf.tolist()):
            x0, y0, x1, y1 = box
            cx_px, cy_px = (x0 + x1) / 2, (y0 + y1) / 2
            # pixel -> map coords (WMS origin is top-left, y flipped)
            map_x = minx + (cx_px / img_w) * (maxx - minx)
            map_y = maxy - (cy_px / img_h) * (maxy - miny)
            lon, lat = _transformer.transform(map_x, map_y)
            raw_detections.append({"tile_id": row["tile_id"], "lon": lon, "lat": lat, "confidence": conf})

    print(f"{len(raw_detections)} raw detections across {len(tiles)} tiles")
    return pd.DataFrame(raw_detections)


def snap_and_dedup(df: pd.DataFrame) -> pd.DataFrame:
    df["lon"], df["lat"] = zip(*df.apply(lambda r: snap_to_nearest_river_point(r["lon"], r["lat"]), axis=1))

    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326").to_crs(epsg=25830)
    gdf = gdf.sort_values("confidence", ascending=False)

    kept_idx, kept_geoms = [], []
    for idx, row in gdf.iterrows():
        if any(row.geometry.distance(g) < DEDUP_RADIUS_M for g in kept_geoms):
            continue
        kept_idx.append(idx)
        kept_geoms.append(row.geometry)

    deduped = gdf.loc[kept_idx].drop(columns="geometry")
    print(f"Deduped ({DEDUP_RADIUS_M}m, keep-highest-confidence): {len(gdf)} -> {len(deduped)}")
    return deduped


if __name__ == "__main__":
    raw = run_inference()
    if raw.empty:
        print("No detections.")
        sys.exit(0)
    deduped = snap_and_dedup(raw)

    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src/layers"))
    from match_ground_truth import match_candidates

    gdf = gpd.GeoDataFrame(deduped, geometry=gpd.points_from_xy(deduped["lon"], deduped["lat"]), crs="EPSG:4326")
    matched = match_candidates(gdf)
    print(matched["match_status"].value_counts())

    matched.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV}")
