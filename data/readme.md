# Dataset Directory

This directory holds every dataset used by the project. 

Parent project entry point: [../README.md](../README.md).

---

## 1. Datasets Used

| Dataset | Modality | Native format | Nominal size | Reference URL (as recorded in `configs/config.yaml`) |
|---|---|---|---:|---|
| Kvasir-SEG | Endoscopic polyp frames + pixel masks | JPG images, PNG masks | 1000 | <https://datasets.simula.no/kvasir-seg/> |
| CVC-ClinicDB | Colonoscopy polyp frames + pixel masks | TIF images, TIF masks | 612 | <https://polyp.grand-challenge.org/CVCClinicDB/> |

- **Kvasir-SEG** is a public gastrointestinal polyp segmentation dataset with pixel-level
  annotations. Its image and mask files share the same stem, so pairing is trivial.
- **CVC-ClinicDB** comes from the CVC polyp challenge and is distributed as TIF frames
  (`Original/`) with TIF ground-truth masks in a separate folder whose name contains a space
  (`Ground Truth/`). Its TIF files may be 16-bit or have unusual channel layouts, which is why
  the conversion script normalises them.

Both datasets are **third-party**.obtain them from their official sources and comply with their terms of use. `.gitignore` notes
that CVC-ClinicDB is restricted to research use. The sizes and URLs above are the values
already recorded in `configs/config.yaml`; they have not been independently re-verified.

---

## 2. Directory Layout

### 2.1 Raw input (must be prepared manually)

```
data/raw/
├── Kvasir-SEG/
│   ├── images/                  # *.jpg  (also .png in some releases)
│   └── masks/                   # *.png  -- same stem as the matching image
└── CVC-ClinicDB/
    ├── Original/                # *.tif
    └── Ground Truth/            # *.tif  -- same stem as the matching image
```

These four paths are the defaults hard-coded in the scripts, and they match the constants in
`scripts/data_pro/visualize_dataset_comparison.py`.

### 2.2 Generated intermediate output

```
data/processed/
├── CVC-ClinicDB-PNG/
│   ├── images/                  # normalised PNG frames
│   └── masks/                   # copied PNG masks (values unchanged)
├── merged_polyp/
│   ├── images/                  # kvasir_<stem>.<ext>, cvc_<stem>.png
│   └── masks/                   # same stems as the images
├── yolo_merged_noaug/           # YOLO segmentation dataset (no augmentation)
│   ├── images/{train,val,test}/
│   ├── labels/{train,val,test}/
│   ├── data.yaml
│   └── split_manifest.json
└── yolo_merged_aug1x/           # same, with augmented copies in the train split

---

## 3. File Naming Rules

| Stage | Rule | Example |
|---|---|---|
| Kvasir raw | upstream name preserved | `cju0qkwl35piu0993l0bia5z6b.jpg` |
| CVC raw | upstream TIF name preserved | `1.tif` |
| CVC PNG | same stem, `.png` extension | `1.png` |
| Merged | `<source-prefix>_<stem>.<ext>` | `kvasir_cju0qkwl35.png`, `cvc_1.png` |
| YOLO label | `<image-stem>.txt` | `cvc_1.txt` |
| Augmented copy (train only) | `<stem>_aug<N>.<ext>` | `cvc_1_aug1.png` |

The prefix is functional, not cosmetic: the split routine derives the source dataset from the
substring before the first `_`, which is how the stratified split is implemented.

---

## 4. Preprocessing Steps and Commands

Run from the repository root, in this order.

### Step 1 — CVC-ClinicDB TIF to PNG

```powershell
python scripts/data_pro/convert_cvc_to_png.py
```

- Input: `data/raw/CVC-ClinicDB/Original`, `data/raw/CVC-ClinicDB/Ground Truth`
- Output: `data/processed/CVC-ClinicDB-PNG/{images,masks}`
- Default `--image-mode native_tiff_rgb`: reads TIF through `tifffile`, min-max normalises to
  8-bit, fixes channel order (RGB to BGR for OpenCV), and handles 1/2/3/4-channel layouts.
- Masks are always written with `--image-mode keep`, so mask pixel values are not altered.
- Other modes: `keep`, `rgb`, `pseudo_rgb` (false-colour, for human inspection only — do not
  train on it).

Requires `tifffile`, which is **not** listed in `requirements.txt` (see
[../README.md](../README.md#41-dependencies-imported-by-the-code-but-absent-from-requirementstxt)).

### Step 2 — Merge both datasets

```powershell
python scripts/data_pro/merge_kvasir_cvc.py
```

- Input: `data/raw/Kvasir-SEG/{images,masks}`, `data/processed/CVC-ClinicDB-PNG/{images,masks}`
- Output: `data/processed/merged_polyp/{images,masks}`
- Overrides: `--kvasir-root`, `--cvc-png-root`, `--output-root`

### Step 3 — Build the YOLO segmentation dataset

Choose exactly one variant:

```powershell
# Baseline (no offline augmentation)
python scripts/data_pro/prepare_yolo_noaug.py

# Offline augmentation of the training split only
python scripts/data_pro/prepare_yolo_aug.py
```

| Flag | No-aug script | Aug script |
|---|---|---|
| `--merged-root` | `data/processed/merged_polyp` | `data/processed/merged_polyp` |
| `--output-root` | `data/processed/yolo_merged_noaug` | `data/processed/yolo_merged_aug1x` |
| `--train-ratio` / `--val-ratio` / `--test-ratio` | `0.8` / `0.1` / `0.1` | `0.8` / `0.1` / `0.1` |
| `--seed` | `42` | `42` |
| `--min-area` | `10.0` | `10.0` |
| `--aug-copies` | — | `1` |

Both scripts **delete `--output-root` before writing** (`shutil.rmtree`). Never point them at a
directory you want to keep.

### Optional — dataset sample figures

```powershell
python scripts/data_pro/visualize_dataset_comparison.py
```

Reads one random sample from each raw dataset and writes `outputs/dataset_comparison/
kvasir_seg_sample.png` and `outputs/dataset_comparison/cvc_clinicdb_sample.png`. This script
requires the raw datasets to be present, and it expects Kvasir images to use the `.jpg`
extension and CVC images the `.tif` extension.

### Optional — synthetic test video for the frontend

```powershell
python scripts/data_pro/create_test_video.py
```

Stitches up to 60 images from `data/processed/yolo_merged_noaug/images/test` into
`static/temp/synthetic_test_video.mp4` (5 FPS, H.264). Useful for exercising the video
detection page without a real endoscopy clip.

---