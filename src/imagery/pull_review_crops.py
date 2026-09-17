"""Pull small, web-sized PNOA crops for the candidate-review tool
(distinct from pull_pnoa_crops.py's 600x600 full-res training crops --
these need to fit many at once inside an Artifact's per-publish size
budget, so smaller pixel dimensions and JPEG compression instead of
PNG).
"""

import io
import os

import pandas as pd
import pyproj
import requests
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WMS_URL = "https://www.ign.es/wms-inspire/pnoa-ma"
LAYER = "OI.OrthoimageCoverage"
CRS = "EPSG:25830"
BUFFER_M = 150
PIXELS = 500  # pulled at this size, then downsized for the web
OUT_SIZE = 380  # final JPEG dimension
JPEG_QUALITY = 78

_transformer = pyproj.Transformer.from_crs("EPSG:4326", CRS, always_xy=True)


def fetch_review_crop(lat: float, lon: float, out_path: str) -> bool:
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
    if not resp.headers.get("content-type", "").startswith("image"):
        return False
    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    img = img.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)
    img.save(out_path, "JPEG", quality=JPEG_QUALITY)
    return True


if __name__ == "__main__":
    import sys

    csv_name = sys.argv[1] if len(sys.argv) > 1 else "review_batch1.csv"
    out_subdir = sys.argv[2] if len(sys.argv) > 2 else "review_crops"
    out_dir = os.path.join(PROJECT_ROOT, "data/raw", out_subdir)
    os.makedirs(out_dir, exist_ok=True)

    df = pd.read_csv(os.path.join(PROJECT_ROOT, "data/processed", csv_name))
    print(f"Pulling {len(df)} review crops from {csv_name}...")

    n_ok = 0
    for _, row in df.iterrows():
        out_path = os.path.join(out_dir, f"{row['candidate_id']}.jpg")
        if os.path.exists(out_path):
            n_ok += 1
            continue
        try:
            ok = fetch_review_crop(row["lat"], row["lon"], out_path)
            n_ok += ok
        except Exception as e:
            print(f"  failed for {row['candidate_id']}: {e}")

    print(f"Done: {n_ok}/{len(df)} crops saved to {out_dir}/")
