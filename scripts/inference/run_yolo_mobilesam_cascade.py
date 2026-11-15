from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.inference.yolo_mobilesam_cascade import CascadePrediction, YoloMobileSamCascade


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

# Edit these defaults directly in code if you do not want to pass arguments in the console.
DEFAULT_SOURCE = PROJECT_ROOT / "data/processed/yolo_merged_noaug/images/test"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs/cascade_runs/test"
DEFAULT_YOLO_WEIGHTS = PROJECT_ROOT / "models/yolov8_seg/best.pt"
DEFAULT_SAM_CHECKPOINT = "mobile_sam.pt"
DEFAULT_SAM_BACKEND = "ultralytics_sam"
DEFAULT_SAM_MODEL_TYPE = "vit_t"
DEFAULT_DEVICE = "cuda"
DEFAULT_CONF = 0.25
DEFAULT_IOU = 0.7
DEFAULT_IMGSZ = 640
DEFAULT_MAX_DET = 300
DEFAULT_BOX_PADDING_RATIO = 0.05


def iter_image_paths(source: Path) -> Iterable[Path]:
    if source.is_file():
        yield source
        return

    if not source.exists():
        raise FileNotFoundError(f"Source path not found: {source}")

    for path in sorted(source.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YOLOv8-seg + MobileSAM cascade inference.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Image file or directory.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory.")
    parser.add_argument("--yolo-weights", type=Path, default=DEFAULT_YOLO_WEIGHTS, help="YOLOv8-seg weights, e.g. best.pt.")
    parser.add_argument("--sam-checkpoint", type=Path, default=DEFAULT_SAM_CHECKPOINT, help="MobileSAM/SAM checkpoint path.")
    parser.add_argument("--sam-backend", choices=["ultralytics_sam", "mobile_sam", "segment_anything"], default=DEFAULT_SAM_BACKEND)
    parser.add_argument(
        "--sam-model-type",
        default=DEFAULT_SAM_MODEL_TYPE,
        help="Model type registered by the chosen backend, e.g. vit_t for MobileSAM or vit_b/vit_l/vit_h for SAM.",
    )
    parser.add_argument("--device", default=DEFAULT_DEVICE, help="Inference device, e.g. cuda, cuda:0, or cpu.")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF, help="YOLO confidence threshold.")
    parser.add_argument("--iou", type=float, default=DEFAULT_IOU, help="YOLO NMS IoU threshold.")
    parser.add_argument("--imgsz", type=int, default=DEFAULT_IMGSZ, help="YOLO inference image size.")
    parser.add_argument("--max-det", type=int, default=DEFAULT_MAX_DET, help="Maximum YOLO detections per image.")
    parser.add_argument("--box-padding-ratio", type=float, default=DEFAULT_BOX_PADDING_RATIO, help="Expand YOLO boxes before SAM prompt.")
    parser.add_argument("--save-overlay", action="store_true", help="Save mask overlay images.")
    parser.add_argument("--save-yolo-mask", action="store_true", help="Save YOLO mask union if available.")
    parser.add_argument("--save-json", action="store_true", help="Save per-image metadata as JSON.")
    return parser


def draw_overlay(image_bgr: np.ndarray, prediction: CascadePrediction) -> np.ndarray:
    overlay = image_bgr.copy()
    mask = prediction.cascade_mask.astype(bool)
    green = np.zeros_like(image_bgr)
    green[:, :, 1] = 255
    overlay = np.where(mask[:, :, None], (0.65 * green + 0.35 * overlay).astype(np.uint8), overlay)

    for item in prediction.items:
        x1, y1, x2, y2 = [int(round(v)) for v in item.box]
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 255, 255), 2)
        label = f"{item.class_name} {item.confidence:.2f}"
        cv2.putText(
            overlay,
            label,
            (x1, max(0, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

    return overlay


def save_outputs(image_path: Path, prediction: CascadePrediction, output_dir: Path, save_overlay: bool, save_yolo_mask: bool, save_json: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = image_path.stem

    mask_path = output_dir / f"{stem}_cascade_mask.png"
    cv2.imwrite(str(mask_path), prediction.cascade_mask.astype(np.uint8) * 255)

    if save_yolo_mask and prediction.yolo_mask is not None:
        yolo_mask = prediction.yolo_mask.astype(np.uint8)
        if yolo_mask.ndim == 3:
            yolo_mask = np.any(yolo_mask, axis=0).astype(np.uint8)
        cv2.imwrite(str(output_dir / f"{stem}_yolo_mask.png"), yolo_mask * 255)

    if save_overlay:
        image_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image_bgr is None:
            raise FileNotFoundError(f"Failed to read image for overlay: {image_path}")
        overlay = draw_overlay(image_bgr, prediction)
        cv2.imwrite(str(output_dir / f"{stem}_overlay.jpg"), overlay)

    if save_json:
        payload = {
            "source": prediction.source,
            "image_shape": list(prediction.image_shape),
            "items": [
                {
                    "box": item.box,
                    "confidence": item.confidence,
                    "class_id": item.class_id,
                    "class_name": item.class_name,
                }
                for item in prediction.items
            ],
        }
        (output_dir / f"{stem}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    missing_paths = []
    if not args.source.exists():
        missing_paths.append(f"source: {args.source}")
    if not args.yolo_weights.exists():
        missing_paths.append(f"yolo_weights: {args.yolo_weights}")
    if args.sam_backend in {"mobile_sam", "segment_anything"} and not args.sam_checkpoint.exists():
        missing_paths.append(f"sam_checkpoint: {args.sam_checkpoint}")

    if missing_paths:
        raise FileNotFoundError(
            "Missing required files or folders for cascade inference: "
            + "; ".join(missing_paths)
            + ". Edit the DEFAULT_* constants at the top of scripts/inference/run_yolo_mobilesam_cascade.py "
            + "or pass explicit command-line arguments."
        )

    cascade = YoloMobileSamCascade(
        yolo_weights=args.yolo_weights,
        sam_checkpoint=args.sam_checkpoint,
        sam_backend=args.sam_backend,
        sam_model_type=args.sam_model_type,
        device=args.device,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        max_det=args.max_det,
        box_padding_ratio=args.box_padding_ratio,
    )

    image_paths = list(iter_image_paths(args.source))
    if not image_paths:
        raise FileNotFoundError(f"No images found in source: {args.source}")

    for image_path in image_paths:
        prediction = cascade.predict(image_path)
        save_outputs(
            image_path=image_path,
            prediction=prediction,
            output_dir=args.output,
            save_overlay=args.save_overlay,
            save_yolo_mask=args.save_yolo_mask,
            save_json=args.save_json,
        )
        print(f"Processed: {image_path.name} -> {args.output}")


if __name__ == "__main__":
    main()
