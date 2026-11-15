# Model Weights

This readme documents how model checkpoints are organised, located, and loaded by this project.

Parent project entry point: [../README.md](../README.md).

---

##  Weight Types Actually Used by This Project

| Weight | Role in this project | Where the path is defined | Present in repo |
|---|---|---|---|
| YOLO segmentation checkpoint (`best.pt`) | Inference backbone of the deployed system | `MODEL_PATH` in `system/backend/config.py` → `models/yolov26-seg-s/best.pt` | no |
| YOLO segmentation checkpoint (`best.pt`) | Default for the eval script and the cascade inference script | `--yolo-weights` defaults in `scripts/eval/compare_yolo_vs_cascade.py` and `scripts/inference/run_yolo_mobilesam_cascade.py` → `models/yolov8_seg/best.pt` | no |
| Ultralytics pretrained `*-seg.pt` | Starting point for training (`--model`, default `yolo11n-seg.pt`) | `scripts/model_train/train_seg_common.py`; downloaded by Ultralytics on first use if the name is not a local file | no |
| SAM / MobileSAM checkpoint | Prompted-refinement stage of the cascade | `DEFAULT_SAM_CHECKPOINT = "mobile_sam.pt"` in `scripts/inference/run_yolo_mobilesam_cascade.py`; `configs/config.yaml` nominally names `models/weights/sam_vit_h_4b8939.pth` (`vit_h`) | no |

---