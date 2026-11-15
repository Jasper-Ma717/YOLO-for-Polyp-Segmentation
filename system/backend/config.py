import os
from pathlib import Path

# 获取项目根目录 (system 文件夹的上一级)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 权重路径，默认使用已训练好的 best.pt
MODEL_PATH = BASE_DIR / "models" / "yolov26-seg-s" / "best.pt"

# 静态资源保存目录
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
RESULT_DIR = STATIC_DIR / "results"

# 数据库文件路径
DATABASE_URL = f"sqlite:///{BASE_DIR}/system/backend/history.db"

# JWT 身份验证配置
SECRET_KEY = "your-very-secret-graduation-key-here"  # 实际应用中请使用环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # token 7天有效

# 确保文件夹存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)
