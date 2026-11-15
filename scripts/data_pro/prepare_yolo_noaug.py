from __future__ import annotations

import argparse
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import yaml


def collect_pairs(image_dir: Path, mask_dir: Path) -> list[tuple[str, Path, Path]]:
    image_map = {p.stem: p for p in image_dir.glob("*") if p.is_file()}
    mask_map = {p.stem: p for p in mask_dir.glob("*") if p.is_file()}
    common = sorted(image_map.keys() & mask_map.keys())
    return [(stem, image_map[stem], mask_map[stem]) for stem in common]


def split_by_source(
    pairs: list[tuple[str, Path, Path]],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> dict[str, list[tuple[str, Path, Path]]]:
    if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-6:
        raise ValueError("train/val/test ratios must sum to 1.0")

    rng = random.Random(seed)
    grouped: dict[str, list[tuple[str, Path, Path]]] = defaultdict(list)
    for item in pairs:
        stem = item[0]
        src = stem.split("_", 1)[0] if "_" in stem else "unknown"
        grouped[src].append(item)

    split_map: dict[str, list[tuple[str, Path, Path]]] = {"train": [], "val": [], "test": []}

    for src, items in grouped.items():
        rng.shuffle(items)
        n = len(items)
        n_train = int(round(n * train_ratio))
        n_val = int(round(n * val_ratio))
        n_test = n - n_train - n_val

        if n_test < 0:
            n_test = 0
            n_val = n - n_train

        train_items = items[:n_train]
        val_items = items[n_train:n_train + n_val]
        test_items = items[n_train + n_val:n_train + n_val + n_test]

        split_map["train"].extend(train_items)
        split_map["val"].extend(val_items)
        split_map["test"].extend(test_items)

        print(f"source={src}: total={n}, train={len(train_items)}, val={len(val_items)}, test={len(test_items)}")

    for k in split_map:
        rng.shuffle(split_map[k])

    return split_map


def mask_to_yolo_segments(mask_path: Path, min_area: float = 10.0) -> list[list[float]]:
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return []

    h, w = mask.shape
    _, binary = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    segments: list[list[float]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue

        contour = contour.reshape(-1, 2)
        if contour.shape[0] < 3:
            continue

        poly: list[float] = []
        for x, y in contour:
            poly.extend([float(x) / float(w), float(y) / float(h)])

        if len(poly) >= 6:
            segments.append(poly)

    return segments


def write_label_file(label_path: Path, segments: list[list[float]], cls_id: int = 0) -> None:
    label_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for seg in segments:
        coords = " ".join(f"{v:.6f}" for v in seg)
        lines.append(f"{cls_id} {coords}")
    label_path.write_text("\n".join(lines), encoding="utf-8")


def copy_and_convert(
    split_name: str,
    items: list[tuple[str, Path, Path]],
    out_root: Path,
    min_area: float,
) -> dict[str, int]:
    out_img_dir = out_root / "images" / split_name
    out_lbl_dir = out_root / "labels" / split_name
    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    image_count = 0
    object_count = 0

    for stem, img_path, mask_path in items:
        dst_img = out_img_dir / f"{stem}{img_path.suffix.lower()}"
        shutil.copy2(img_path, dst_img)

        segments = mask_to_yolo_segments(mask_path, min_area=min_area)
        dst_lbl = out_lbl_dir / f"{stem}.txt"
        write_label_file(dst_lbl, segments, cls_id=0)

        image_count += 1
        object_count += len(segments)

    return {"images": image_count, "objects": object_count}


def write_data_yaml(out_root: Path) -> Path:
    data = {
        "path": str(out_root).replace("\\", "/"),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {0: "polyp"},
    }
    yaml_path = out_root / "data.yaml"
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    return yaml_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare merged polyp data into YOLO-seg format without augmentation.")
    parser.add_argument("--merged-root", type=Path, default=Path("data/processed/merged_polyp"), help="Merged dataset root with images/ and masks/.")
    parser.add_argument("--output-root", type=Path, default=Path("data/processed/yolo_merged_noaug"), help="Output YOLO dataset root.")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-area", type=float, default=10.0, help="Minimum mask contour area to keep.")
    args = parser.parse_args()

    image_dir = args.merged_root / "images"
    mask_dir = args.merged_root / "masks"

    if not image_dir.exists() or not mask_dir.exists():
        raise FileNotFoundError(f"Missing merged images/masks in {args.merged_root}")

    pairs = collect_pairs(image_dir, mask_dir)
    if not pairs:
        raise RuntimeError("No paired image/mask files found.")

    print(f"paired samples found: {len(pairs)}")

    split_map = split_by_source(
        pairs,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    out_root = args.output_root
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    summary: dict[str, dict[str, int]] = {}
    for split_name in ["train", "val", "test"]:
        summary[split_name] = copy_and_convert(
            split_name=split_name,
            items=split_map[split_name],
            out_root=out_root,
            min_area=args.min_area,
        )

    yaml_path = write_data_yaml(out_root)

    manifest = {
        "total_pairs": len(pairs),
        "ratios": {
            "train": args.train_ratio,
            "val": args.val_ratio,
            "test": args.test_ratio,
        },
        "seed": args.seed,
        "min_area": args.min_area,
        "summary": summary,
        "data_yaml": str(yaml_path).replace("\\", "/"),
    }
    (out_root / "split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("YOLO dataset prepared")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
