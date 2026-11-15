from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import DetectionHistory, Patient, User, get_db
from ..utils.audit import write_audit_log
from ..utils.security import get_current_admin, get_password_hash

router = APIRouter()


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="physician", pattern="^(physician|admin)$")


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(pattern="^(physician|admin)$")


class UpdateUserPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)


def serialize_user(user: User):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at,
    }


@router.get("/users")
def list_users(
    keyword: str | None = None,
    role: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    query = db.query(User)
    if keyword:
        query = query.filter(User.username.ilike(f"%{keyword.strip()}%"))
    if role in {"physician", "admin"}:
        query = query.filter(User.role == role)

    users = query.order_by(User.created_at.desc()).all()
    return {"status": "success", "data": [serialize_user(user) for user in users]}


@router.post("/users")
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    existed_user = db.query(User).filter(User.username == payload.username).first()
    if existed_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=payload.username,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    write_audit_log(db, admin_user, "create_user", f"新增用户 {user.username}，角色 {user.role}", target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)

    return {"status": "success", "message": "用户创建成功", "data": serialize_user(user)}


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.id == admin_user.id and payload.role != "admin":
        raise HTTPException(status_code=400, detail="不能将当前登录管理员降级")

    user.role = payload.role
    write_audit_log(db, admin_user, "update_user_role", f"将用户 {user.username} 角色更新为 {payload.role}", target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)

    return {"status": "success", "message": "角色更新成功", "data": serialize_user(user)}


@router.post("/users/{user_id}/password")
def update_user_password(
    user_id: int,
    payload: UpdateUserPasswordRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.hashed_password = get_password_hash(payload.new_password)
    write_audit_log(db, admin_user, "reset_user_password", f"重置用户 {user.username} 密码", target_type="user", target_id=user.id)
    db.commit()

    return {"status": "success", "message": "用户密码已更新"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin_user: User = Depends(get_current_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    patient_ids = [row.id for row in db.query(Patient.id).filter(Patient.doctor_id == user.id).all()]
    if patient_ids:
        db.query(DetectionHistory).filter(DetectionHistory.patient_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(DetectionHistory).filter(DetectionHistory.user_id == user.id).delete(synchronize_session=False)
    db.query(Patient).filter(Patient.doctor_id == user.id).delete(synchronize_session=False)

    username = user.username
    write_audit_log(db, admin_user, "delete_user", f"删除用户 {username}", target_type="user", target_id=user.id)
    db.delete(user)
    db.commit()
    return {"status": "success", "message": "用户已删除"}
