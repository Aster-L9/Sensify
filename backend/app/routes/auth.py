from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, ActivityLog, UserRole
from app.schemas import (
    UserCreate, UserLogin, TokenResponse, UserResponse, RefreshRequest, PasswordChange,
)
from app.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse)
def register(data: UserCreate, db: Session = Depends(get_db)):
    username = data.username.strip()
    email = data.email.strip().lower()

    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    # Self-registration always creates an analyst; the admin account is pre-seeded only
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(data.password),
        role=UserRole.analyst.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Log activity
    db.add(ActivityLog(
        user_id=user.id, action="register",
        details=f"New analyst registered: {user.username}",
    ))
    db.commit()

    access_token = create_access_token({"sub": user.id, "role": user.role})
    refresh_token = create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/change-password")
def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    current_user.hashed_password = hash_password(data.new_password)
    db.commit()

    db.add(ActivityLog(
        user_id=current_user.id, action="password_changed",
        details=f"User changed password: {current_user.username}",
    ))
    db.commit()

    return {"message": "Password changed successfully"}


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Log activity
    db.add(ActivityLog(
        user_id=user.id, action="login",
        details=f"User login: {user.username}",
    ))
    db.commit()

    access_token = create_access_token({"sub": user.id, "role": user.role})
    refresh_token = create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(data: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = create_access_token({"sub": user.id, "role": user.role})
    new_refresh = create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
