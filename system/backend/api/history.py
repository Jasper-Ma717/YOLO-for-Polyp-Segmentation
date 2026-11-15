from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from ..database import DetectionHistory, Patient, User, get_db
from ..utils.audit import write_audit_log
from ..utils.security import get_current_user

router = APIRouter()


def serialize_history(record: DetectionHistory):
    return {
        "id": record.id,
        "task_type": record.task_type,
        "filename": record.filename,
        "polyp_count": record.polyp_count,
        "processing_time_ms": record.processing_time_ms,
        "inference_time_ms": record.inference_time_ms,
        "saved_path": record.saved_path,
        "user_id": record.user_id,
        "patient_id": record.patient_id,
        "doctor_username": record.user.username if record.user else None,
        "patient_name": record.patient.name if record.patient else None,
        "created_at": record.created_at,
    }


def create_patient_report(patient: Patient, records: list[DetectionHistory]):
    buffer = BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ChineseTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=18,
        leading=24,
    )
    body_style = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10,
        leading=15,
    )

    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=36, bottomMargin=36, leftMargin=36, rightMargin=36)
    elements = []

    total_records = len(records)
    positive_records = len([item for item in records if item.polyp_count > 0])
    avg_inference = round(sum(item.inference_time_ms or 0 for item in records) / total_records, 2) if total_records else 0

    elements.append(Paragraph("息肉智能诊断系统患者检测报告", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"患者姓名：{patient.name}", body_style))
    elements.append(Paragraph(f"年龄 / 性别：{patient.age} / {patient.gender}", body_style))
    elements.append(Paragraph(f"病史信息：{patient.medical_history or '无'}", body_style))
    elements.append(Paragraph(f"检测记录数：{total_records}，阳性记录数：{positive_records}，平均推理耗时：{avg_inference} ms", body_style))
    elements.append(Spacer(1, 12))

    table_data = [["记录ID", "任务类型", "文件名", "息肉数", "处理耗时(ms)", "推理耗时(ms)", "检测时间"]]
    for item in records:
        table_data.append([
            str(item.id),
            "图片" if item.task_type == "image" else "视频",
            item.filename,
            str(item.polyp_count),
            f"{item.processing_time_ms:.2f}",
            f"{item.inference_time_ms:.2f}",
            item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "-",
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer


@router.get("/")
def get_history(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(DetectionHistory)
    if current_user.role != "admin":
        query = query.filter(DetectionHistory.user_id == current_user.id)

    records = query.order_by(DetectionHistory.created_at.desc()).limit(limit).all()

    return {
        "status": "success",
        "data": [serialize_history(r) for r in records],
    }


@router.get("/patient/{patient_id}/report-pdf")
def export_patient_report(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    if current_user.role != "admin" and patient.doctor_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权导出该患者报告")

    query = db.query(DetectionHistory).filter(DetectionHistory.patient_id == patient_id)
    if current_user.role != "admin":
        query = query.filter(DetectionHistory.user_id == current_user.id)
    records = query.order_by(DetectionHistory.created_at.desc()).all()

    buffer = create_patient_report(patient, records)
    write_audit_log(db, current_user, "export_patient_report", f"导出患者 {patient.name} PDF 报告", target_type="patient", target_id=patient.id)
    db.commit()

    filename = f"patient_{patient.id}_report.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{history_id}")
def delete_history(history_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    h = db.query(DetectionHistory).filter(DetectionHistory.id == history_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="记录不存在")
    if current_user.role != "admin" and h.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除")
    write_audit_log(db, current_user, "delete_history", f"删除检测记录 {h.id}", target_type="history", target_id=h.id)
    db.delete(h)
    db.commit()
    return {"status": "success"}


class UpdateHistory(BaseModel):
    polyp_count: int


@router.patch("/{history_id}")
def update_history(history_id: int, data: UpdateHistory, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    h = db.query(DetectionHistory).filter(DetectionHistory.id == history_id).first()
    if not h:
        raise HTTPException(status_code=404, detail="记录不存在")
    if current_user.role != "admin" and h.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改")
    h.polyp_count = data.polyp_count
    write_audit_log(db, current_user, "update_history", f"修改检测记录 {h.id} 的息肉数量为 {data.polyp_count}", target_type="history", target_id=h.id)
    db.commit()
    return {"status": "success", "polyp_count": h.polyp_count}
