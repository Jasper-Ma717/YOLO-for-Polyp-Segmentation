import cv2
import os
import glob
from pathlib import Path

def create_test_video():
    # 获取测试集图片路径
    base_dir = Path(__file__).resolve().parent.parent.parent
    image_folder = base_dir / 'data' / 'processed' / 'yolo_merged_noaug' / 'images' / 'test'
    output_dir = base_dir / 'static' / 'temp'
    output_dir.mkdir(parents=True, exist_ok=True)
    video_name = output_dir / 'synthetic_test_video.mp4'

    # 寻找所有的图片 (jpg或png)
    images = []
    for ext in ['*.jpg', '*.png']:
        images.extend(glob.glob(str(image_folder / ext)))
        
    # 对图片进行排序
    images.sort()

    if not images:
        print(f"在 {image_folder} 中未找到图片，无法生成测试视频。")
        return

    # 限制视频长度（比如取前 60 张图片，生成一个短视频）
    images = images[:60]
    print(f"找到 {len(images)} 张图片，开始合成测试视频...")

    # 读取第一张图片来获取视频的分辨率
    frame = cv2.imread(images[0])
    height, width, layers = frame.shape

    # 使用 imageio 结合 libx264 输出浏览器兼容的 MP4 视频
    import imageio
    out = imageio.get_writer(str(video_name), fps=5.0, codec='libx264', format='FFMPEG')

    for image_path in images:
        img_bgr = cv2.imread(image_path)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        
        # 调整所有图片到一致的大小
        img_resized = cv2.resize(img_rgb, (width, height))
        out.append_data(img_resized)

    out.close()
    print(f"✅ 测试视频已成功生成: {video_name}")

if __name__ == "__main__":
    create_test_video()
