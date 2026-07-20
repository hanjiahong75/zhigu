"""Authentication service: JWT + password hashing."""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from ..models.stock import User

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "zhigu-jwt-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-SHA256 with random salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against PBKDF2-SHA256 hash."""
    try:
        salt, stored_hash = hashed_password.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return secrets.compare_digest(dk.hex(), stored_hash)
    except (ValueError, AttributeError):
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def create_user(db: Session, username: str, password: str, nickname: str = "") -> User | None:
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return None
    user = User(
        username=username,
        password_hash=hash_password(password),
        nickname=nickname or username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def update_profile(db: Session, user_id: int, nickname: str = None, avatar: str = None) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    if nickname is not None:
        user.nickname = nickname
    if avatar is not None:
        user.avatar = avatar
    db.commit()
    return True


def change_password(db: Session, user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "用户不存在"
    if not verify_password(old_password, user.password_hash):
        return False, "原密码错误"
    if len(new_password) < 6:
        return False, "新密码至少6位"
    user.password_hash = hash_password(new_password)
    db.commit()
    return True, "密码修改成功"


def get_user_by_id(db: Session, user_id: int) -> dict | None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "created_at": user.created_at.isoformat() if user.created_at else "",
    }
