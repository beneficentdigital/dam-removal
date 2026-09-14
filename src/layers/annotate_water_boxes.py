"""Fast bounding-box generation for the micro-pilot proof-of-concept:
color-threshold water segmentation instead of SAM. Chosen under time
pressure (2026-09-13, presenting Monday) over downloading/running SAM's
model checkpoint -- disclosed simplification, not the full pilot's
planned samgeo-assisted manual workflow (plan.md stage 3).

Works because our confirmed-good crops are almost all reservoirs/dams
with strong water-vs-farmland color contrast, and each crop is centered
on the known point, so we take the connected component nearest center.
"""

import os
from typing import Optional

import cv2
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CROPS_DIR = os.path.join(PROJECT_ROOT, "data/raw/micro_pilot_crops_train")
OUT_CSV = os.path.join(PROJECT_ROOT, "data/processed/micro_pilot_boxes.csv")


def segment_water_box(img_path: str) -> Optional[tuple]:
    img = cv2.imread(img_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Water in these crops is blue-green to dark-green/near-black;
    # farmland is tan/brown (low saturation-ish, high value, warm hue).
    lower = np.array([35, 25, 20])
    upper = np.array([140, 255, 220])
    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))

    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
    if n_labels <= 1:
        return None

    h, w = mask.shape
    center = np.array([w / 2, h / 2])
    # Among components that overlap the middle half of the crop (the water
    # body should be near the known point, even if not pixel-perfect
    # centered), pick the LARGEST -- not just nearest-to-center, since a
    # small bright-edge fragment can sit closer to center than the true
    # full water extent.
    best, best_area = None, 0
    for label in range(1, n_labels):
        area = stats[label, cv2.CC_STAT_AREA]
        if area < 400:
            continue
        dist = np.linalg.norm(centroids[label] - center)
        if dist > min(h, w) * 0.35:
            continue
        if area > best_area:
            best, best_area = label, area

    if best is None:
        return None

    x, y, bw, bh, area = stats[best]
    return (x, y, x + bw, y + bh)


if __name__ == "__main__":
    df = pd.read_csv(os.path.join(PROJECT_ROOT, "data/processed/micro_pilot_filtered_set.csv"))
    rows = []
    n_ok = 0
    for _, row in df.iterrows():
        filename = f"{row['source']}_{row['source_id']}.png".replace("/", "_")
        img_path = os.path.join(CROPS_DIR, filename)
        if not os.path.exists(img_path):
            print(f"  missing file: {filename}")
            continue
        box = segment_water_box(img_path)
        if box is None:
            print(f"  no water segment found: {filename}")
            continue
        x0, y0, x1, y1 = box
        rows.append({**row.to_dict(), "filename": filename, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
        n_ok += 1

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT_CSV, index=False)
    print(f"\nGenerated boxes for {n_ok}/{len(df)} crops -> {OUT_CSV}")
