from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

import cv2
import numpy as np
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass
class SampleMetrics:
    image: str
    dice_yolo: float
    iou_yolo: float
    dice_cascade: float
    iou_cascade: float


def iter_image_paths(source: Path) -> Iterable[Path]:
    if source.is_file():
        yield source
        return

    for path in sorted(source.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def load_binary_mask(mask_path: Path, target_shape: Optional[tuple[int, int]] = None) -> np.ndarray:
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise FileNotFoundError(f"Failed to read mask: {mask_path}")
    if target_shape is not None and mask.shape[:2] != target_shape:
        mask = cv2.resize(mask, (target_shape[1], target_shape[0]), interpolation=cv2.INTER_NEAREST)
    return mask > 0


def normalize_mask(mask: np.ndarray) -> np.ndarray:
    array = np.asarray(mask)
    if array.ndim == 3 and array.shape[-1] == 1:
        array = array[..., 0]
    if array.ndim != 2:
        raise ValueError(f"Expected a 2D mask, got shape {array.shape}")
    return array.astype(bool)


def union_yolo_masks(result) -> np.ndarray:
    if result.masks is None:
        height, width = result.orig_shape[:2]
        return np.zeros((height, width), dtype=bool)
    mask_data = result.masks.data.cpu().numpy()
    if mask_data.ndim == 3:
        return np.any(mask_data, axis=0)
    return mask_data.astype(bool)


def dice_iou(pred: np.ndarray, target: np.ndarray) -> tuple[float, float]:
    pred_bool = normalize_mask(pred)
    target_bool = normalize_mask(target)
    intersection = np.logical_and(pred_bool, target_bool).sum(dtype=np.float64)
    pred_sum = pred_bool.sum(dtype=np.float64)
    target_sum = target_bool.sum(dtype=np.float64)
    union = np.logical_or(pred_bool, target_bool).sum(dtype=np.float64)

    dice = 1.0 if pred_sum + target_sum == 0 else float(2.0 * intersection / (pred_sum + target_sum))
    iou = 1.0 if union == 0 else float(intersection / union)
    return dice, iou


def save_markdown(summary_path: Path, rows: list[SampleMetrics], yolo_stats: dict[str, float], cascade_stats: dict[str, float]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# YOLO vs Cascade Evaluation",
        "",
        f"Samples: {len(rows)}",
        "",
        "## Aggregate Metrics",
        "",
        "| Method | Dice | IoU |",
        "|---|---:|---:|",
        f"| YOLO | {yolo_stats['dice']:.4f} | {yolo_stats['iou']:.4f} |",
        f"| Cascade | {cascade_stats['dice']:.4f} | {cascade_stats['iou']:.4f} |",
        f"| Improvement | {cascade_stats['dice'] - yolo_stats['dice']:+.4f} | {cascade_stats['iou'] - yolo_stats['iou']:+.4f} |",
        "",
        "## Per-sample Files",
        "",
        "Per-image metrics are stored in the companion JSON file.",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def save_json(summary_path: Path, rows: list[SampleMetrics], yolo_stats: dict[str, float], cascade_stats: dict[str, float], output_path: Path) -> None:
    payload = {
        "samples": [asdict(row) for row in rows],
        "summary": {
            "yolo": yolo_stats,
            "cascade": cascade_stats,
            "improvement": {
                "dice": cascade_stats["dice"] - yolo_stats["dice"],
                "iou": cascade_stats["iou"] - yolo_stats["iou"],
            },
        },
        "markdown_report": str(summary_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare YOLO baseline against cascade masks on the test split.")
    parser.add_argument("--source", type=Path, default=PROJECT_ROOT / "data/processed/yolo_merged_noaug/images/test")
    parser.add_argument("--gt-mask-dir", type=Path, default=PROJECT_ROOT / "data/processed/merged_polyp/masks")
    parser.add_argument("--cascade-mask-dir", type=Path, default=PROJECT_ROOT / "outputs/cascade_runs/test")
    parser.add_argument("--yolo-weights", type=Path, default=PROJECT_ROOT / "models/yolov8_seg/best.pt")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "outputs/eval")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.7)
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--max-det", type=int, default=300)
    return parser


def evaluate() -> None:
    args = build_arg_parser().parse_args()

    if not args.source.exists():
        raise FileNotFoundError(f"Source directory not found: {args.source}")
    if not args.gt_mask_dir.exists():
        raise FileNotFoundError(f"GT mask directory not found: {args.gt_mask_dir}")
    if not args.cascade_mask_dir.exists():
        raise FileNotFoundError(f"Cascade mask directory not found: {args.cascade_mask_dir}")

    model = YOLO(str(args.yolo_weights))

    rows: list[SampleMetrics] = []
    yolo_dice_values: list[float] = []
    yolo_iou_values: list[float] = []
    cascade_dice_values: list[float] = []
    cascade_iou_values: list[float] = []

    for image_path in iter_image_paths(args.source):
        gt_mask_path = args.gt_mask_dir / f"{image_path.stem}.png"
        cascade_mask_path = args.cascade_mask_dir / f"{image_path.stem}_cascade_mask.png"

        if not gt_mask_path.exists():
            continue
        if not cascade_mask_path.exists():
            continue

        image_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image_bgr is None:
            continue
        height, width = image_bgr.shape[:2]

        gt_mask = load_binary_mask(gt_mask_path, (height, width))
        cascade_mask = load_binary_mask(cascade_mask_path, (height, width))

        yolo_result = model.predict(
            source=image_bgr,
            conf=args.conf,
            iou=args.iou,
            imgsz=args.imgsz,
            device=args.device,
            max_det=args.max_det,
            verbose=False,
        )[0]
        yolo_mask = union_yolo_masks(yolo_result)
        if yolo_mask.shape[:2] != (height, width):
            yolo_mask = cv2.resize(yolo_mask.astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST) > 0

        dice_yolo, iou_yolo = dice_iou(yolo_mask, gt_mask)
        dice_cascade, iou_cascade = dice_iou(cascade_mask, gt_mask)

        rows.append(
            SampleMetrics(
                image=image_path.name,
                dice_yolo=dice_yolo,
                iou_yolo=iou_yolo,
                dice_cascade=dice_cascade,
                iou_cascade=iou_cascade,
            )
        )
        yolo_dice_values.append(dice_yolo)
        yolo_iou_values.append(iou_yolo)
        cascade_dice_values.append(dice_cascade)
        cascade_iou_values.append(iou_cascade)

    if not rows:
        raise RuntimeError("No matched samples were found for evaluation.")

    yolo_stats = {
        "dice": float(np.mean(yolo_dice_values)),
        "iou": float(np.mean(yolo_iou_values)),
        "samples": len(rows),
    }
    cascade_stats = {
        "dice": float(np.mean(cascade_dice_values)),
        "iou": float(np.mean(cascade_iou_values)),
        "samples": len(rows),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = args.output_dir / "yolo_vs_cascade_summary.md"
    json_path = args.output_dir / "yolo_vs_cascade_summary.json"
    csv_path = args.output_dir / "yolo_vs_cascade_per_sample.csv"

    save_markdown(markdown_path, rows, yolo_stats, cascade_stats)
    save_json(markdown_path, rows, yolo_stats, cascade_stats, json_path)

    lines = ["image,dice_yolo,iou_yolo,dice_cascade,iou_cascade"]
    for row in rows:
        lines.append(
            f"{row.image},{row.dice_yolo:.6f},{row.iou_yolo:.6f},{row.dice_cascade:.6f},{row.iou_cascade:.6f}"
        )
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Saved summary: {markdown_path}")
    print(f"Saved json    : {json_path}")
    print(f"Saved csv     : {csv_path}")
    print("\nAggregate metrics")
    print(f"  YOLO    Dice={yolo_stats['dice']:.4f} IoU={yolo_stats['iou']:.4f}")
    print(f"  Cascade Dice={cascade_stats['dice']:.4f} IoU={cascade_stats['iou']:.4f}")
    print(f"  Gain    Dice={cascade_stats['dice'] - yolo_stats['dice']:+.4f} IoU={cascade_stats['iou'] - yolo_stats['iou']:+.4f}")


if __name__ == "__main__":
    evaluate()
