"""
数据集对比可视化脚本
绘制Kvasir-SEG和CVC-ClinicDB两个息肉数据集的样本对比图

布局:
- 每个数据集单独一张图，1x2 子图：原图 | 掩码
- 统一画布 + 等比例填充，所有子图尺寸一致
"""

import os
import random
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from PIL import Image
import numpy as np
import cv2

# ========== 中文支持 ==========
for font_name in ['SimHei', 'Microsoft YaHei', 'KaiTi']:
    try:
        fm.findfont(font_name, fallback_to_default=False)
        plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
        break
    except Exception:
        continue
plt.rcParams['axes.unicode_minus'] = False

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 数据集路径
KVASIR_IMAGES_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "Kvasir-SEG", "images")
KVASIR_MASKS_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "Kvasir-SEG", "masks")
CVC_IMAGES_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "CVC-ClinicDB", "Original")
CVC_MASKS_DIR = os.path.join(PROJECT_ROOT, "data", "raw", "CVC-ClinicDB", "Ground Truth")

# 统一画布尺寸 (宽, 高)
CANVAS_SIZE = (512, 512)
CANVAS_BG_COLOR = (0, 0, 0)
CANVAS_BG_MASK = (0, 0, 0)


def fit_to_canvas(img, target_size=CANVAS_SIZE, bg_color=CANVAS_BG_COLOR):
    """
    将图像等比例缩放后居中放置于统一画布上
    """
    if isinstance(img, Image.Image):
        img_array = np.array(img)
    else:
        img_array = img

    h, w = img_array.shape[:2]
    target_w, target_h = target_size

    scale = min(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    if new_h != h or new_w != w:
        if len(img_array.shape) == 2:
            resized = cv2.resize(img_array, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        else:
            resized = cv2.resize(img_array, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    else:
        resized = img_array

    if len(img_array.shape) == 2:
        canvas = np.full((target_h, target_w), bg_color[0], dtype=np.uint8)
    else:
        canvas = np.full((target_h, target_w, 3), bg_color, dtype=np.uint8)

    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

    return canvas


def get_sample_images(kvasir_idx=None, cvc_idx=None):
    """
    获取两个数据集的样本图像
    """
    kvasir_images = sorted([f for f in os.listdir(KVASIR_IMAGES_DIR) if f.endswith('.jpg')])
    cvc_images = sorted([f for f in os.listdir(CVC_IMAGES_DIR) if f.endswith('.tif')])

    if kvasir_idx is None:
        kvasir_idx = random.randint(0, len(kvasir_images) - 1)
    if cvc_idx is None:
        cvc_idx = random.randint(0, len(cvc_images) - 1)

    # Kvasir-SEG
    kvasir_img_name = kvasir_images[kvasir_idx]
    kvasir_img_path = os.path.join(KVASIR_IMAGES_DIR, kvasir_img_name)
    kvasir_mask_path = os.path.join(KVASIR_MASKS_DIR, kvasir_img_name)

    kvasir_image = Image.open(kvasir_img_path).convert('RGB')
    kvasir_mask = np.array(Image.open(kvasir_mask_path).convert('L'))

    # CVC-ClinicDB
    cvc_img_name = cvc_images[cvc_idx]
    cvc_img_path = os.path.join(CVC_IMAGES_DIR, cvc_img_name)
    cvc_mask_path = os.path.join(CVC_MASKS_DIR, cvc_img_name)

    cvc_image = cv2.imread(cvc_img_path)
    cvc_image = cv2.cvtColor(cvc_image, cv2.COLOR_BGR2RGB)
    cvc_mask = cv2.imread(cvc_mask_path, cv2.IMREAD_GRAYSCALE)

    return kvasir_image, kvasir_mask, cvc_image, cvc_mask


def save_dataset_figure(image, mask, save_path, figsize=(8, 5)):
    """
    保存单个数据集的对比图（1x2：原图 | 掩码）
    """
    img_canvas = fit_to_canvas(image, CANVAS_SIZE, CANVAS_BG_COLOR)
    mask_canvas = fit_to_canvas(mask, CANVAS_SIZE, CANVAS_BG_MASK)

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    axes[0].imshow(img_canvas)
    axes[0].axis('off')
    axes[0].set_xlabel('原图', fontsize=14, fontweight='bold', labelpad=8)

    axes[1].imshow(mask_canvas, cmap='gray')
    axes[1].axis('off')
    axes[1].set_xlabel('掩码', fontsize=14, fontweight='bold', labelpad=8)

    plt.tight_layout()

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"图像已保存至: {save_path}")


def get_dataset_statistics():
    """
    获取数据集统计信息
    """
    kvasir_images = [f for f in os.listdir(KVASIR_IMAGES_DIR) if f.endswith('.jpg')]
    cvc_images = [f for f in os.listdir(CVC_IMAGES_DIR) if f.endswith('.tif')]

    kvasir_sample = Image.open(os.path.join(KVASIR_IMAGES_DIR, kvasir_images[0]))
    cvc_sample = cv2.imread(os.path.join(CVC_IMAGES_DIR, cvc_images[0]))

    stats = {
        'Kvasir-SEG': {
            'count': len(kvasir_images),
            'format': 'JPG',
            'sample_size': kvasir_sample.size,
        },
        'CVC-ClinicDB': {
            'count': len(cvc_images),
            'format': 'TIF',
            'sample_size': (cvc_sample.shape[1], cvc_sample.shape[0]),
        }
    }
    return stats


if __name__ == "__main__":
    stats = get_dataset_statistics()
    print("\n=== 数据集统计信息 ===")
    for name, info in stats.items():
        print(f"\n{name}:")
        print(f"  - 样本数量: {info['count']}")
        print(f"  - 图像格式: {info['format']}")
        print(f"  - 样本尺寸: {info['sample_size']}")

    # 获取样本
    kvasir_image, kvasir_mask, cvc_image, cvc_mask = get_sample_images()

    output_dir = os.path.join(PROJECT_ROOT, "outputs", "dataset_comparison")

    # Kvasir-SEG 单独一张图
    print("\n=== 生成 Kvasir-SEG 样本图 ===")
    save_dataset_figure(
        kvasir_image, kvasir_mask,
        save_path=os.path.join(output_dir, "kvasir_seg_sample.png"),
        figsize=(8, 5)
    )

    # CVC-ClinicDB 单独一张图
    print("\n=== 生成 CVC-ClinicDB 样本图 ===")
    save_dataset_figure(
        cvc_image, cvc_mask,
        save_path=os.path.join(output_dir, "cvc_clinicdb_sample.png"),
        figsize=(8, 5)
    )
