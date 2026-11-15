from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import ACCESS_TOKEN_EXPIRE_MINUTES
from ..database import User, get_db
from ..utils.audit import write_audit_log
from ..utils.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="physician")


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existed_user = db.query(User).filter(User.username == payload.username).first()
    if existed_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    if payload.role not in {"physician", "admin"}:
        raise HTTPException(status_code=400, detail="角色必须是 physician 或 admin")

    user = User(
        username=payload.username,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_audit_log(db, user, "register", f"用户 {user.username} 注册成功", target_type="user", target_id=user.id)
    db.commit()

    return {
        "status": "success",
        "message": "注册成功",
        "data": {"id": user.id, "username": user.username, "role": user.role},
    }


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "uid": user.id, "role": user.role},
        expires_delta=access_token_expires,
    )
    write_audit_log(db, user, "login", f"用户 {user.username} 登录系统", target_type="user", target_id=user.id)
    db.commit()

    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "role": user.role},
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "status": "success",
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "created_at": current_user.created_at,
        },
    }


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")

    current_user.hashed_password = get_password_hash(payload.new_password)
    write_audit_log(db, current_user, "change_password", "修改个人密码", target_type="user", target_id=current_user.id)
    db.commit()

    return {"status": "success", "message": "密码修改成功"}
