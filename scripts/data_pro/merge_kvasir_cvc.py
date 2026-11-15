from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def stem_set(folder: Path, pattern: str) -> set[str]:
    return {p.stem for p in folder.glob(pattern)}


def find_file_by_stem(folder: Path, stem: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"):
        p = folder / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def copy_pair(src_img: Path, src_mask: Path, out_img: Path, out_mask: Path) -> None:
    out_img.parent.mkdir(parents=True, exist_ok=True)
    out_mask.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_img, out_img)
    shutil.copy2(src_mask, out_mask)


def merge_one_dataset(
    image_dir: Path,
    mask_dir: Path,
    out_image_dir: Path,
    out_mask_dir: Path,
    prefix: str,
) -> tuple[int, int, int]:
    image_stems = stem_set(image_dir, "*")
    mask_stems = stem_set(mask_dir, "*")
    common = sorted(image_stems & mask_stems)

    ok = 0
    fail = 0
    for stem in common:
        src_img = find_file_by_stem(image_dir, stem)
        src_mask = find_file_by_stem(mask_dir, stem)
        if src_img is None or src_mask is None:
            fail += 1
            continue

        dst_img = out_image_dir / f"{prefix}_{stem}{src_img.suffix.lower()}"
        dst_mask = out_mask_dir / f"{prefix}_{stem}{src_mask.suffix.lower()}"
        copy_pair(src_img, src_mask, dst_img, dst_mask)
        ok += 1

    return len(common), ok, fail


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Kvasir-SEG and converted CVC-ClinicDB PNG into one folder.")
    parser.add_argument(
        "--kvasir-root",
        type=Path,
        default=Path("data/raw/Kvasir-SEG"),
        help="Path of Kvasir-SEG root directory.",
    )
    parser.add_argument(
        "--cvc-png-root",
        type=Path,
        default=Path("data/processed/CVC-ClinicDB-PNG"),
        help="Path of converted CVC PNG directory.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/processed/merged_polyp"),
        help="Output path for merged images/masks.",
    )
    args = parser.parse_args()

    out_images = args.output_root / "images"
    out_masks = args.output_root / "masks"

    k_common, k_ok, k_fail = merge_one_dataset(
        args.kvasir_root / "images",
        args.kvasir_root / "masks",
        out_images,
        out_masks,
        prefix="kvasir",
    )

    c_common, c_ok, c_fail = merge_one_dataset(
        args.cvc_png_root / "images",
        args.cvc_png_root / "masks",
        out_images,
        out_masks,
        prefix="cvc",
    )

    print("Dataset merge finished")
    print(f"Kvasir common pairs: {k_common}, merged: {k_ok}, failed: {k_fail}")
    print(f"CVC common pairs: {c_common}, merged: {c_ok}, failed: {c_fail}")
    print(f"Total merged: {k_ok + c_ok}")
    print(f"Merged images dir: {out_images}")
    print(f"Merged masks dir: {out_masks}")


if __name__ == "__main__":
    main()
