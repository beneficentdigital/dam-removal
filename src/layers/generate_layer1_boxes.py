"""Generate Layer 1 training boxes for the real pilot's 66-crop training
set, via the same automated color-threshold heuristic proven in the
micro-pilot (annotate_water_boxes.py) rather than manual SAM-assisted
annotation.

This is the actual plan.md stage 3 approach after constitution.md's
2026-09-14 revision: "Reversed under explicit time pressure... in favor
of the faster color-threshold heuristic + YOLOv8n approach proven in
the micro-pilot... Speed now explicitly outweighs the marginal accuracy
gain from manual annotation." tasks.md's T019/T020 (SAM click-through
workflow) describe the superseded plan and were never updated -- this
script is the real T019/T020.
"""

import os

import cv2
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CROPS_DIR = os.path.join(PROJECT_ROOT, "data/raw/pnoa_crops")
IN_CSV = os.path.join(PROJECT_ROOT, "data/processed/layer1_annotation_training_set.csv")
OUT_CSV = os.path.join(PROJECT_ROOT, "data/processed/layer1_boxes.csv")


def segment_water_box(img_path: str):
    """Same heuristic as annotate_water_boxes.py: water in these PNOA
    crops is blue-green to dark-green/near-black, farmland/bare ground
    is tan/brown -- pick the largest near-center connected component."""
    img = cv2.imread(img_path)
    if img is None:
        return None
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
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
    # Reject near-full-frame boxes: found 2026-09-16 comparing against
    # this training set's real crops -- 28/58 initial boxes were exactly
    # (0,0,600,600), a qualitatively different failure from "the water
    # body happens to be large" (the micro-pilot's proven run only hit
    # this 5/28 times). Visually, these are crops with no dam visible at
    # all (a georeferencing gap, or a barrier type too small/underground
    # to show from above) -- the threshold catches roads/shadow across
    # the whole frame as one connected blob instead. Better to report
    # "no reliable box" than train on a label that says "the object is
    # the entire image."
    if (bw * bh) / (w * h) > 0.85:
        return None
    return (x, y, x + bw, y + bh)


if __name__ == "__main__":
    df = pd.read_csv(IN_CSV)
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
