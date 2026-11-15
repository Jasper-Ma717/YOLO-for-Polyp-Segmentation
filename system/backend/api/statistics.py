from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db, DetectionHistory, Patient, User
from ..utils.security import get_current_user

router = APIRouter()


@router.get("/overview")
def get_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取数据统计总览，医生仅看自己的数据，管理员看全局。"""
    is_admin = current_user.role == "admin"

    # ---- 基础查询过滤 ----
    det_query = db.query(DetectionHistory)
    pat_query = db.query(Patient)
    if not is_admin:
        det_query = det_query.filter(DetectionHistory.user_id == current_user.id)
        pat_query = pat_query.filter(Patient.doctor_id == current_user.id)

    # 1. 汇总指标
    total_detections = det_query.count()
    total_patients = pat_query.count()
    total_images = det_query.filter(DetectionHistory.task_type == "image").count()
    total_videos = det_query.filter(DetectionHistory.task_type == "video").count()

    avg_processing = db.query(func.avg(DetectionHistory.processing_time_ms))
    avg_inference = db.query(func.avg(DetectionHistory.inference_time_ms))
    if not is_admin:
        avg_processing = avg_processing.filter(DetectionHistory.user_id == current_user.id)
        avg_inference = avg_inference.filter(DetectionHistory.user_id == current_user.id)
    avg_processing_ms = avg_processing.scalar() or 0
    avg_inference_ms = avg_inference.scalar() or 0

    # 2. 有息肉 vs 无息肉
    polyp_pos = det_query.filter(DetectionHistory.polyp_count > 0).count()
    polyp_neg = total_detections - polyp_pos

    # 3. 按日期汇总检测量（最近 30 天）
    daily_query = db.query(
        func.date(DetectionHistory.created_at).label("date"),
        func.count().label("count"),
    )
    if not is_admin:
        daily_query = daily_query.filter(DetectionHistory.user_id == current_user.id)
    daily_query = (
        daily_query
        .group_by(func.date(DetectionHistory.created_at))
        .order_by(func.date(DetectionHistory.created_at).desc())
        .limit(30)
    )
    daily_data = [{"date": str(row.date), "count": row.count} for row in daily_query.all()]

    # 4. 按任务类型汇总
    type_dist = [
        {"type": "图片检测", "count": total_images},
        {"type": "视频检测", "count": total_videos},
    ]

    # 5. 患者检测频次 Top 5
    top_patients_query = (
        db.query(
            Patient.name,
            func.count(DetectionHistory.id).label("det_count"),
        )
        .join(Patient, DetectionHistory.patient_id == Patient.id)
    )
    if not is_admin:
        top_patients_query = top_patients_query.filter(DetectionHistory.user_id == current_user.id)
    top_patients_query = (
        top_patients_query
        .group_by(Patient.name)
        .order_by(func.count(DetectionHistory.id).desc())
        .limit(5)
    )
    top_patients = [{"name": r.name, "count": r.det_count} for r in top_patients_query.all()]

    # 6. 管理员专属：医生工作量排行
    doctor_workload = []
    if is_admin:
        workload_query = (
            db.query(
                User.username,
                func.count(DetectionHistory.id).label("det_count"),
            )
            .join(User, DetectionHistory.user_id == User.id)
            .group_by(User.username)
            .order_by(func.count(DetectionHistory.id).desc())
            .all()
        )
        doctor_workload = [{"username": r.username, "count": r.det_count} for r in workload_query]

    return {
        "status": "success",
        "data": {
            "total_detections": total_detections,
            "total_patients": total_patients,
            "total_images": total_images,
            "total_videos": total_videos,
            "avg_processing_ms": round(avg_processing_ms, 2),
            "avg_inference_ms": round(avg_inference_ms, 2),
            "polyp_positive": polyp_pos,
            "polyp_negative": polyp_neg,
            "daily_trend": daily_data,
            "type_distribution": type_dist,
            "top_patients": top_patients,
            "doctor_workload": doctor_workload,
        },
    }
