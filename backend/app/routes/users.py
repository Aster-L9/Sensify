from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import User, ActivityLog
from app.schemas import UserResponse, UserUpdate, UserCreateAdmin
from app.auth import get_current_user, require_admin, hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/", response_model=UserResponse)
def create_user(
    data: UserCreateAdmin,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    raise HTTPException(status_code=403, detail="Account creation is disabled.")


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active

    db.commit()
    db.refresh(user)

    db.add(ActivityLog(
        user_id=admin.id, action="user_updated",
        entity_type="user", entity_id=user.id,
        details=f"Admin updated user: {user.username}",
    ))
    db.commit()

    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    raise HTTPException(status_code=403, detail="Account deletion is disabled.")
