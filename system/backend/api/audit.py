from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import AuditLog, User, get_db
from ..utils.security import get_current_admin

router = APIRouter()


@router.get("/logs")
def get_audit_logs(
    limit: int = 200,
    action: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)

    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return {
        "status": "success",
        "data": [
            {
                "id": log.id,
                "username": log.user.username if log.user else None,
                "action": log.action,
                "detail": log.detail,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }
