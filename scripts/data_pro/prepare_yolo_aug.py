from __future__ import annotations

import argparse
import json
import os
import random
import shutil
from collections import defaultdict
from pathlib import Path

# Work around duplicate OpenMP runtime loading on some Windows Conda stacks.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import albumentations as A
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


def mask_array_to_yolo_segments(mask: np.ndarray, min_area: float = 10.0) -> list[list[float]]:
    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

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


def build_kvasir_transform() -> A.Compose:
    return A.Compose(
        [
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.2),
            A.RandomRotate90(p=0.4),
            A.Affine(
                scale=(0.9, 1.15),
                translate_percent=(-0.06, 0.06),
                rotate=(-20, 20),
                shear=(-8, 8),
                interpolation=cv2.INTER_LINEAR,
                mask_interpolation=cv2.INTER_NEAREST,
                border_mode=cv2.BORDER_REFLECT_101,
                p=0.6,
            ),
            A.ElasticTransform(alpha=25, sigma=5, interpolation=cv2.INTER_LINEAR, border_mode=cv2.BORDER_REFLECT_101, p=0.15),
            A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
            A.HueSaturationValue(hue_shift_limit=8, sat_shift_limit=14, val_shift_limit=10, p=0.25),
            A.CLAHE(clip_limit=(1, 3), tile_grid_size=(8, 8), p=0.2),
            A.GaussianBlur(blur_limit=(3, 5), p=0.1),
        ]
    )


def build_cvc_transform() -> A.Compose:
    return A.Compose(
        [
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.15),
            A.RandomRotate90(p=0.3),
            A.Affine(
                scale=(0.95, 1.1),
                translate_percent=(-0.05, 0.05),
                rotate=(-15, 15),
                shear=(-6, 6),
                interpolation=cv2.INTER_LINEAR,
                mask_interpolation=cv2.INTER_NEAREST,
                border_mode=cv2.BORDER_REFLECT_101,
                p=0.5,
            ),
            A.RandomBrightnessContrast(brightness_limit=0.28, contrast_limit=0.28, p=0.6),
            A.RandomGamma(gamma_limit=(85, 125), p=0.3),
            A.CLAHE(clip_limit=(1, 3), tile_grid_size=(8, 8), p=0.3),
            A.GaussianBlur(blur_limit=(3, 5), p=0.12),
        ]
    )


def choose_transform(stem: str, tf_kvasir: A.Compose, tf_cvc: A.Compose) -> A.Compose:
    if stem.startswith("cvc_"):
        return tf_cvc
    return tf_kvasir


def copy_item(
    stem: str,
    img: np.ndarray,
    mask: np.ndarray,
    image_suffix: str,
    out_img_dir: Path,
    out_lbl_dir: Path,
    min_area: float,
) -> tuple[int, int]:
    out_img_path = out_img_dir / f"{stem}{image_suffix}"
    out_lbl_path = out_lbl_dir / f"{stem}.txt"

    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(out_img_path), img)
    segments = mask_array_to_yolo_segments(mask, min_area=min_area)
    write_label_file(out_lbl_path, segments, cls_id=0)
    return 1, len(segments)


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
    parser = argparse.ArgumentParser(description="Prepare merged data into YOLO-seg format with train-only augmentation.")
    parser.add_argument("--merged-root", type=Path, default=Path("data/processed/merged_polyp"), help="Merged dataset root with images/ and masks/.")
    parser.add_argument("--output-root", type=Path, default=Path("data/processed/yolo_merged_aug1x"), help="Output YOLO dataset root.")
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-area", type=float, default=10.0)
    parser.add_argument("--aug-copies", type=int, default=1, help="How many augmented variants to create per train image.")
    args = parser.parse_args()

    if args.aug_copies < 1:
        raise ValueError("aug-copies must be >= 1")

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

    tf_kvasir = build_kvasir_transform()
    tf_cvc = build_cvc_transform()

    summary: dict[str, dict[str, int]] = {
        "train": {"images": 0, "objects": 0},
        "val": {"images": 0, "objects": 0},
        "test": {"images": 0, "objects": 0},
    }

    for split_name in ["train", "val", "test"]:
        out_img_dir = out_root / "images" / split_name
        out_lbl_dir = out_root / "labels" / split_name

        for stem, img_path, mask_path in split_map[split_name]:
            img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if img is None or mask is None:
                continue

            c_img, c_obj = copy_item(
                stem=stem,
                img=img,
                mask=mask,
                image_suffix=img_path.suffix.lower(),
                out_img_dir=out_img_dir,
                out_lbl_dir=out_lbl_dir,
                min_area=args.min_area,
            )
            summary[split_name]["images"] += c_img
            summary[split_name]["objects"] += c_obj

            if split_name != "train":
                continue

            transform = choose_transform(stem, tf_kvasir=tf_kvasir, tf_cvc=tf_cvc)
            for i in range(args.aug_copies):
                aug = transform(image=img, mask=mask)
                aug_img = aug["image"]
                aug_mask = aug["mask"]
                aug_stem = f"{stem}_aug{i + 1}"
                c_img, c_obj = copy_item(
                    stem=aug_stem,
                    img=aug_img,
                    mask=aug_mask,
                    image_suffix=img_path.suffix.lower(),
                    out_img_dir=out_img_dir,
                    out_lbl_dir=out_lbl_dir,
                    min_area=args.min_area,
                )
                summary[split_name]["images"] += c_img
                summary[split_name]["objects"] += c_obj

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
        "aug_copies": args.aug_copies,
        "summary": summary,
        "data_yaml": str(yaml_path).replace("\\", "/"),
    }
    (out_root / "split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("YOLO augmented dataset prepared")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
