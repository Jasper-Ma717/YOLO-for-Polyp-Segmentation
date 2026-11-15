from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import tifffile


def collect_tif_stems(folder: Path) -> set[str]:
    return {p.stem for p in folder.glob("*.tif")}


def normalize_to_u8(image):
    if image.dtype == "uint8":
        return image
    min_val = float(image.min())
    max_val = float(image.max())
    if max_val <= min_val:
        return (image * 0).astype("uint8")
    scaled = (image.astype("float32") - min_val) * (255.0 / (max_val - min_val))
    return scaled.astype("uint8")


def read_with_tifffile(path: Path):
    arr = tifffile.imread(str(path))
    if arr is None:
        return None
    return arr


def to_three_channel(image):
    if len(image.shape) == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if len(image.shape) == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


def robust_native_rgb_from_tiff(path: Path):
    arr = read_with_tifffile(path)
    if arr is None:
        return None

    arr = normalize_to_u8(arr)
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)

    if arr.ndim == 3:
        if arr.shape[0] == 3 and arr.shape[2] != 3:
            arr = arr.transpose(1, 2, 0)
        if arr.shape[2] > 3:
            arr = arr[:, :, :3]
        if arr.shape[2] == 3:
            # tifffile returns channels in RGB order; OpenCV writes BGR arrays.
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        if arr.shape[2] == 1:
            return cv2.cvtColor(arr[:, :, 0], cv2.COLOR_GRAY2BGR)

    # Fallback for uncommon layouts
    flat = arr.reshape(arr.shape[0], arr.shape[1]) if arr.ndim > 2 else arr
    return cv2.cvtColor(normalize_to_u8(flat), cv2.COLOR_GRAY2BGR)


def convert_image_mode(image, mode: str):
    if mode == "keep":
        return image

    image_u8 = normalize_to_u8(image)
    image_3c = to_three_channel(image_u8)

    if mode == "rgb":
        return image_3c

    # Pseudo color mapping turns single-channel endoscopy frames into
    # visible RGB-like images for human inspection while keeping masks intact.
    if mode == "pseudo_rgb":
        if len(image_u8.shape) == 3:
            gray = cv2.cvtColor(image_u8, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_u8
        return cv2.applyColorMap(gray, cv2.COLORMAP_TURBO)

    raise ValueError(f"Unsupported image mode: {mode}")


def convert_one(src: Path, dst: Path, image_mode: str = "keep", use_tiff_native: bool = False) -> bool:
    img = None
    if use_tiff_native:
        img = robust_native_rgb_from_tiff(src)
    if img is None:
        img = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
    if img is None:
        return False
    img = convert_image_mode(img, mode=image_mode)
    dst.parent.mkdir(parents=True, exist_ok=True)
    return cv2.imwrite(str(dst), img)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert CVC-ClinicDB tif images/masks to png format.")
    parser.add_argument(
        "--cvc-root",
        type=Path,
        default=Path("data/raw/CVC-ClinicDB"),
        help="Path of raw CVC-ClinicDB directory.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/processed/CVC-ClinicDB-PNG"),
        help="Output directory for converted PNG files.",
    )
    parser.add_argument(
        "--image-mode",
        type=str,
        choices=["keep", "rgb", "pseudo_rgb", "native_tiff_rgb"],
        default="native_tiff_rgb",
        help="Image conversion mode for CVC Original.",
    )
    args = parser.parse_args()

    src_images = args.cvc_root / "Original"
    src_masks = args.cvc_root / "Ground Truth"

    out_images = args.output_root / "images"
    out_masks = args.output_root / "masks"

    if not src_images.exists() or not src_masks.exists():
        raise FileNotFoundError(
            f"CVC source folders not found: {src_images} and/or {src_masks}")

    image_stems = collect_tif_stems(src_images)
    mask_stems = collect_tif_stems(src_masks)
    common_stems = sorted(image_stems & mask_stems)

    only_images = sorted(image_stems - mask_stems)
    only_masks = sorted(mask_stems - image_stems)

    ok_count = 0
    fail_count = 0
    image_mode = args.image_mode

    for stem in common_stems:
        img_ok = convert_one(
            src_images / f"{stem}.tif",
            out_images / f"{stem}.png",
            image_mode="rgb" if image_mode == "native_tiff_rgb" else image_mode,
            use_tiff_native=(image_mode == "native_tiff_rgb"),
        )
        mask_ok = convert_one(
            src_masks / f"{stem}.tif",
            out_masks / f"{stem}.png",
            image_mode="keep",
        )

        if img_ok and mask_ok:
            ok_count += 1
        else:
            fail_count += 1

    print("CVC tif -> png conversion finished")
    print(f"paired samples: {len(common_stems)}")
    print(f"success: {ok_count}")
    print(f"failed: {fail_count}")
    print(f"only in images: {len(only_images)}")
    print(f"only in masks: {len(only_masks)}")
    print(f"image mode: {image_mode}")
    print(f"output images: {out_images}")
    print(f"output masks: {out_masks}")


if __name__ == "__main__":
    main()
