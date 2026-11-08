from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import ApiError
from ..models import User
from ..schemas import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.email == body.email))
    if exists is not None:
        raise ApiError(409, "EMAIL_ALREADY_EXISTS", "Пользователь с таким email уже существует.")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return RegisterResponse(user_id=user.id, token=create_token(user.id))


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == (body.email or "").strip().lower()))
    if user is None or not verify_password(body.password or "", user.password_hash):
        raise ApiError(401, "AUTH_FAILED", "Неверный email или пароль.")
    return LoginResponse(token=create_token(user.id))
