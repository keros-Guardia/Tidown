"""
Panel administrateur — accessible uniquement à l'utilisateur admin.
Gestion des utilisateurs, changement de mot de passe forcé.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import List, Optional

from database import get_db
from models import User
from auth import get_current_admin, get_password_hash, verify_password
from schemas import UserOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _to_out(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "lastfm_username": u.lastfm_username,
        "has_lastfm_api_key": bool(u.lastfm_api_key),
        "is_admin": bool(u.is_admin),
        "created_at": u.created_at,
    }


class CreateUserBody(BaseModel):
    username: str
    email: EmailStr
    password: str
    is_admin: bool = False


class SetPasswordBody(BaseModel):
    new_password: str


class UpdateUserBody(BaseModel):
    email: Optional[EmailStr] = None
    is_admin: Optional[bool] = None


# ── Utilisateurs ──────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.id))
    return [_to_out(u) for u in result.scalars().all()]


@router.post("/users")
async def create_user(
    body: CreateUserBody,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nom d'utilisateur ou email déjà utilisé")

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit faire au moins 8 caractères")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=get_password_hash(body.password),
        is_admin=1 if body.is_admin else 0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _to_out(user)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    body: UpdateUserBody,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if body.email is not None:
        user.email = body.email
    if body.is_admin is not None:
        # Empêcher l'admin de se retirer ses propres droits
        if user.id == admin.id and not body.is_admin:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas retirer vos propres droits admin")
        user.is_admin = 1 if body.is_admin else 0

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _to_out(user)


@router.post("/users/{user_id}/set-password")
async def set_user_password(
    user_id: int,
    body: SetPasswordBody,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Le mot de passe doit faire au moins 8 caractères")

    user.hashed_password = get_password_hash(body.new_password)
    db.add(user)
    await db.commit()
    return {"message": f"Mot de passe de {user.username} mis à jour"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")

    await db.delete(user)
    await db.commit()
    return {"message": f"Utilisateur {user.username} supprimé"}
