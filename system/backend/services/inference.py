import cv2
import time
import os
import imageio
from pathlib import Path
from ultralytics import YOLO
from ..config import MODEL_PATH, RESULT_DIR

# 单例模式加载模型，避免每次请求重复加载
class YoloService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(YoloService, cls).__new__(cls)
            cls._instance.load_model()
        return cls._instance

    def load_model(self):
        print(f"Loading YOLO model from {MODEL_PATH}...")
        try:
            self.model = YOLO(str(MODEL_PATH))
            print("Model loaded successfully.")
        except Exception as e:
            print(f"Failed to load model from {MODEL_PATH}. Error: {e}")
            self.model = None

    def predict_image(self, image_path: str, filename: str):
        if not self.model:
            raise Exception("Model not loaded.")
        
        start_time = time.time()
        
        # 运行推理
        results = self.model.predict(source=image_path, save=False, conf=0.5)
        result = results[0]
        
        inference_time_ms = 0.0
        if hasattr(result, 'speed'):
            inference_time_ms = sum(result.speed.values())
        
        # 获取息肉数量
        polyp_count = len(result.boxes) if result.boxes else 0
        
        # 渲染结果图像
        annotated_img = result.plot()
        
        # 保存结果图
        result_filename = f"res_img_{filename}"
        result_path = RESULT_DIR / result_filename
        cv2.imwrite(str(result_path), annotated_img)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return {
            "polyp_count": polyp_count,
            "processing_time_ms": processing_time_ms,
            "inference_time_ms": inference_time_ms,
            "result_path": str(result_path),
            "result_filename": result_filename
        }

    def process_video(self, video_path: str, filename: str):
        if not self.model:
            raise Exception("Model not loaded.")
            
        start_time = time.time()
        cap = cv2.VideoCapture(video_path)
        
        # 获取视频属性
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            fps = 25.0
        
        result_filename = f"res_vid_{filename}"
        result_path = RESULT_DIR / result_filename
        
        # 使用 imageio 结合 libx264 输出浏览器高度兼容的 MP4 视频
        # Streamlit 的 st.video 依赖 H264 编码，OpenCV 的默认 mp4v 无法播放
        out = imageio.get_writer(str(result_path), fps=fps, codec='libx264', format='FFMPEG')
        
        total_polyps = 0
        frame_count = 0
        inference_time_ms = 0.0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_count += 1
            # YOLO 模型对于 np 数组默认为 BGR 色彩空间，这里传入 frame(BGR) 没问题
            results = self.model.predict(source=frame, save=False, conf=0.25, verbose=False)
            result = results[0]
            
            if hasattr(result, 'speed'):
                inference_time_ms += sum(result.speed.values())
            
            polyp_count = len(result.boxes) if result.boxes else 0
            if polyp_count > 0:
                total_polyps += polyp_count
                
            annotated_frame = result.plot() # 返回的是 BGR 图像
            
            # 写入视频时，imageio 期望 RGB 图像，我们需要进行转换
            annotated_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
            out.append_data(annotated_rgb)
            
        cap.release()
        out.close()
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return {
            "polyp_count": total_polyps,
            "processing_time_ms": processing_time_ms,
            "inference_time_ms": inference_time_ms,
            "result_path": str(result_path),
            "result_filename": result_filename,
            "total_frames": frame_count
        }

# 初始化公共单例
yolo_service = YoloService()
