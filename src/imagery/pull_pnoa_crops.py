"""Pull real high-resolution PNOA crops around specific dam points, via
IGN's public WMS (not Earth Engine's incomplete PNOA10 mirror -- see
research-brief.md). Used for Layer 1 annotation (T019/T020): each of
the 66 training-set dams needs a close-up crop to draw a bounding box
on, not a whole 5km tile.

No auth needed -- plain OGC WMS 1.3.0 GetMap requests.
"""

import os
import sys

import pandas as pd
import pyproj
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WMS_URL = "https://www.ign.es/wms-inspire/pnoa-ma"
LAYER = "OI.OrthoimageCoverage"
CRS = "EPSG:25830"
BUFFER_M = 150  # crop half-width around each point
PIXELS = 600  # -> 0.5m/pixel at this buffer size
OUT_DIR = os.path.join(PROJECT_ROOT, "data/raw/pnoa_crops")

_transformer = pyproj.Transformer.from_crs("EPSG:4326", CRS, always_xy=True)


def fetch_crop(lat: float, lon: float, out_path: str) -> bool:
    x, y = _transformer.transform(lon, lat)
    bbox = f"{x - BUFFER_M},{y - BUFFER_M},{x + BUFFER_M},{y + BUFFER_M}"
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetMap",
        "LAYERS": LAYER,
        "STYLES": "",
        "CRS": CRS,
        "BBOX": bbox,
        "WIDTH": PIXELS,
        "HEIGHT": PIXELS,
        "FORMAT": "image/png",
    }
    resp = requests.get(WMS_URL, params=params, timeout=30)
    resp.raise_for_status()
    if resp.headers.get("content-type", "").startswith("image"):
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return True
    print(f"  unexpected response for {out_path}: {resp.headers.get('content-type')}")
    return False


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(os.path.join(PROJECT_ROOT, "data/processed/layer1_annotation_training_set.csv"))
    print(f"Pulling PNOA crops for {len(df)} training-set dams...")

    n_ok = 0
    for _, row in df.iterrows():
        filename = f"{row['source']}_{row['source_id']}.png".replace("/", "_")
        out_path = os.path.join(OUT_DIR, filename)
        try:
            ok = fetch_crop(row["lat"], row["lon"], out_path)
            n_ok += ok
        except Exception as e:
            print(f"  failed for {row['source_id']}: {e}")

    print(f"Done: {n_ok}/{len(df)} crops saved to {OUT_DIR}/")
