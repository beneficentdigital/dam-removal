"""Fine-tune a YOLOv8 detector on the micro-pilot's 26 boxes. Uses
axis-aligned YOLOv8 (not RBOD's oriented-box variant) and starts from
Ultralytics' pretrained checkpoint rather than RBOD's own weights --
both are disclosed time-boxed simplifications for the proof-of-concept
(2026-09-13), not the full pilot's planned approach (plan.md stage 3).
"""

import os
import shutil

import pandas as pd
from PIL import Image

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CROPS_DIR = os.path.join(PROJECT_ROOT, "data/raw/micro_pilot_crops_train")
DATASET_DIR = os.path.join(PROJECT_ROOT, "data/processed/yolo_dataset")
IMG_SIZE = 600  # our crops are 600x600


def build_yolo_dataset():
    df = pd.read_csv(os.path.join(PROJECT_ROOT, "data/processed/micro_pilot_boxes_final.csv"))
    img_dir = os.path.join(DATASET_DIR, "images/train")
    lbl_dir = os.path.join(DATASET_DIR, "labels/train")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(lbl_dir, exist_ok=True)

    for _, row in df.iterrows():
        src = os.path.join(CROPS_DIR, row["filename"])
        stem = row["filename"].replace(".png", "")
        shutil.copy(src, os.path.join(img_dir, row["filename"]))

        # YOLO format: class x_center y_center width height, all normalized 0-1
        xc = (row["x0"] + row["x1"]) / 2 / IMG_SIZE
        yc = (row["y0"] + row["y1"]) / 2 / IMG_SIZE
        bw = (row["x1"] - row["x0"]) / IMG_SIZE
        bh = (row["y1"] - row["y0"]) / IMG_SIZE
        with open(os.path.join(lbl_dir, f"{stem}.txt"), "w") as f:
            f.write(f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n")

    yaml_content = f"""path: {DATASET_DIR}
train: images/train
val: images/train
names:
  0: barrier
"""
    yaml_path = os.path.join(DATASET_DIR, "dataset.yaml")
    with open(yaml_path, "w") as f:
        f.write(yaml_content)
    print(f"Built YOLO dataset: {len(df)} images -> {DATASET_DIR}")
    return yaml_path


if __name__ == "__main__":
    yaml_path = build_yolo_dataset()

    from ultralytics import YOLO

    model = YOLO("yolov8n.pt")  # nano checkpoint -- fastest for this proof-of-concept
    model.train(data=yaml_path, epochs=50, imgsz=IMG_SIZE, batch=8, project=DATASET_DIR, name="run", verbose=False)
    print("Training complete.")
