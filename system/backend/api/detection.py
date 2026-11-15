from fastapi import APIRouter, File, UploadFile, Depends, Form, HTTPException
from sqlalchemy.orm import Session
import shutil
import uuid
from ..database import get_db, DetectionHistory, User, Patient
from ..services.inference import yolo_service
from ..config import UPLOAD_DIR
from ..utils.audit import write_audit_log
from ..utils.security import get_current_user

router = APIRouter()

@router.post("/image")
async def detect_image(
    patient_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    if current_user.role != "admin" and patient.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该患者")

    # 保存上传的文件
    unique_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    upload_path = UPLOAD_DIR / unique_filename
    
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 调用推理服务
    try:
        result = yolo_service.predict_image(str(upload_path), unique_filename)
        
        # 保存到数据库
        db_record = DetectionHistory(
            task_type="image",
            filename=file.filename,
            polyp_count=result["polyp_count"],
            processing_time_ms=result["processing_time_ms"],
            inference_time_ms=result["inference_time_ms"],
            saved_path=result["result_filename"],
            user_id=current_user.id,
            patient_id=patient.id,
        )
        db.add(db_record)
        db.flush()
        write_audit_log(
            db,
            current_user,
            "detect_image",
            f"对患者 {patient.name} 执行图片检测: {file.filename}",
            target_type="history",
            target_id=db_record.id,
        )
        db.commit()
        db.refresh(db_record)
        
        return {
            "status": "success",
            "message": "Image processed",
            "data": {
                "patient_id": patient.id,
                "doctor_id": current_user.id,
                "polyp_count": result["polyp_count"],
                "processing_time_ms": result["processing_time_ms"],
                "inference_time_ms": result["inference_time_ms"],
                "result_filename": result["result_filename"]
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/video")
async def detect_video(
    patient_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    if current_user.role != "admin" and patient.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该患者")

    unique_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    upload_path = UPLOAD_DIR / unique_filename
    
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        result = yolo_service.process_video(str(upload_path), unique_filename)
        
        db_record = DetectionHistory(
            task_type="video",
            filename=file.filename,
            polyp_count=result["polyp_count"],
            processing_time_ms=result["processing_time_ms"],
            inference_time_ms=result["inference_time_ms"],
            saved_path=result["result_filename"],
            user_id=current_user.id,
            patient_id=patient.id,
        )
        db.add(db_record)
        db.flush()
        write_audit_log(
            db,
            current_user,
            "detect_video",
            f"对患者 {patient.name} 执行视频检测: {file.filename}",
            target_type="history",
            target_id=db_record.id,
        )
        db.commit()
        db.refresh(db_record)
        
        return {
            "status": "success",
            "message": "Video processed",
            "data": {
                "patient_id": patient.id,
                "doctor_id": current_user.id,
                "polyp_count": result["polyp_count"],
                "processing_time_ms": result["processing_time_ms"],
                "inference_time_ms": result["inference_time_ms"],
                "result_filename": result["result_filename"]
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
