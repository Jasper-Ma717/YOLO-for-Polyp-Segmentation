from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.orm import Session

from ..database import Patient, User, DetectionHistory, get_db
from ..utils.audit import write_audit_log
from ..utils.security import get_current_user

router = APIRouter()


class PatientCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    age: int = Field(ge=0, le=130)
    gender: str = Field(min_length=1, max_length=32)
    medical_history: str = Field(default="", max_length=2000)


class PatientUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    age: Optional[int] = Field(default=None, ge=0, le=130)
    gender: Optional[str] = Field(default=None, min_length=1, max_length=32)
    medical_history: Optional[str] = Field(default=None, max_length=2000)


@router.post("/")
def create_patient(
    payload: PatientCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = Patient(
        name=payload.name,
        age=payload.age,
        gender=payload.gender,
        medical_history=payload.medical_history,
        doctor_id=current_user.id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    write_audit_log(db, current_user, "create_patient", f"创建患者档案: {patient.name}", target_type="patient", target_id=patient.id)
    db.commit()

    return {
        "status": "success",
        "message": "患者创建成功",
        "data": {
            "id": patient.id,
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "medical_history": patient.medical_history,
            "doctor_id": patient.doctor_id,
            "created_at": patient.created_at,
        },
    }


@router.get("/mine")
def list_my_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Patient)
    if current_user.role != "admin":
        query = query.filter(Patient.doctor_id == current_user.id)

    patients = query.order_by(Patient.created_at.desc()).all()
    return {
        "status": "success",
        "data": [
            {
                "id": p.id,
                "name": p.name,
                "age": p.age,
                "gender": p.gender,
                "medical_history": p.medical_history,
                "doctor_id": p.doctor_id,
                "created_at": p.created_at,
            }
            for p in patients
        ],
    }


@router.put("/{patient_id}")
def update_patient(
    patient_id: int,
    payload: PatientUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    if current_user.role != "admin" and patient.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限修改该患者")

    if payload.name is not None:
        patient.name = payload.name
    if payload.age is not None:
        patient.age = payload.age
    if payload.gender is not None:
        patient.gender = payload.gender
    if payload.medical_history is not None:
        patient.medical_history = payload.medical_history

    write_audit_log(db, current_user, "update_patient", f"更新患者档案: {patient.name}", target_type="patient", target_id=patient.id)
    db.commit()
    db.refresh(patient)

    return {
        "status": "success",
        "message": "患者信息已更新",
        "data": {
            "id": patient.id,
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "medical_history": patient.medical_history,
            "doctor_id": patient.doctor_id,
            "created_at": patient.created_at,
        },
    }


@router.delete("/{patient_id}")
def delete_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    if current_user.role != "admin" and patient.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限删除该患者")

    patient_name = patient.name
    # 同时删除该患者关联的检测记录
    db.query(DetectionHistory).filter(DetectionHistory.patient_id == patient_id).delete()
    write_audit_log(db, current_user, "delete_patient", f"删除患者档案: {patient_name}", target_type="patient", target_id=patient_id)
    db.delete(patient)
    db.commit()

    return {"status": "success", "message": "患者及其关联检测记录已删除"}
