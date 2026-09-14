"""Evaluate the fine-tuned micro-pilot model against the 13 held-out
dams -- these were never used in training or box-generation, so this is
the real "does this work at all" check (FR-007a's held-out principle,
applied at micro-pilot scale).

Each holdout crop is centered on the known dam's real-world coordinate,
so "detected" means: at least one predicted box's center falls within
the middle third of the image (a generous proxy for "found the known
structure," appropriate for a fast proof-of-concept check).
"""

import glob
import os

from ultralytics import YOLO

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(PROJECT_ROOT, "data/processed/yolo_dataset/run/weights/best.pt")
HOLDOUT_DIR = os.path.join(PROJECT_ROOT, "data/raw/micro_pilot_crops_holdout")
IMG_SIZE = 600
# Visually confirmed to show no structure at all (bad ground-truth
# coordinate, not a model failure) -- excluded from the recall count.
NO_STRUCTURE = {"AMBER_63433029-C3A2-4190"}

if __name__ == "__main__":
    model = YOLO(MODEL_PATH)
    files = sorted(glob.glob(f"{HOLDOUT_DIR}/*.png"))
    files = [f for f in files if not any(bad in f for bad in NO_STRUCTURE)]
    print(f"Evaluating {len(files)} held-out dams with confirmed visible structures "
          f"(never seen during training)...")

    n_detected = 0
    for f in files:
        results = model.predict(f, verbose=False, conf=0.15)
        r = results[0]
        found_center = False
        for box in r.boxes:
            xc, yc, _, _ = box.xywh[0].tolist()
            if IMG_SIZE / 3 < xc < 2 * IMG_SIZE / 3 and IMG_SIZE / 3 < yc < 2 * IMG_SIZE / 3:
                found_center = True
        status = "DETECTED" if found_center else "missed"
        n_boxes = len(r.boxes)
        print(f"  {os.path.basename(f)}: {status} ({n_boxes} total boxes, conf>=0.15)")
        n_detected += found_center

    print(f"\nHeld-out recall: {n_detected}/{len(files)} ({100*n_detected/len(files):.0f}%)")
