from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import datetime
from .config import DATABASE_URL

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 定义用户(医生/管理员)表
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="physician") # physician, admin
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patients = relationship("Patient", back_populates="doctor")
    detections = relationship("DetectionHistory", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

# 定义患者病历表
class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    age = Column(Integer)
    gender = Column(String)
    medical_history = Column(String, default="")
    doctor_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    doctor = relationship("User", back_populates="patients")
    detections = relationship("DetectionHistory", back_populates="patient")

# 定义检测历史表结构
class DetectionHistory(Base):
    __tablename__ = "detection_history"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String, index=True)      # 'image' 或 'video'
    filename = Column(String)                   # 原始文件名
    polyp_count = Column(Integer, default=0)    # 检测到的息肉掩膜数量或视频中的总息肉帧次
    processing_time_ms = Column(Float)          # 整个处理耗时 (毫秒)
    inference_time_ms = Column(Float, default=0.0) # 模型推理用时 (毫秒)
    saved_path = Column(String)                 # 结果图像或视频保存路径
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)     # 绑定经手医生
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True) # 绑定患者

    user = relationship("User", back_populates="detections")
    patient = relationship("Patient", back_populates="detections")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, index=True)
    detail = Column(String, default="")
    target_type = Column(String, nullable=True)
    target_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="audit_logs")

# 初始化数据库
def init_db():
    Base.metadata.create_all(bind=engine)

# 获取数据库会话依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
