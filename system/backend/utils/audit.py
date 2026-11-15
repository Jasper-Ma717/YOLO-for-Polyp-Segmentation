from sqlalchemy.orm import Session

from ..database import AuditLog, User


def write_audit_log(
    db: Session,
    user: User | None,
    action: str,
    detail: str = "",
    target_type: str | None = None,
    target_id: int | None = None,
):
    log = AuditLog(
        user_id=user.id if user else None,
        action=action,
        detail=detail,
        target_type=target_type,
        target_id=target_id,
    )
    db.add(log)
    return log
