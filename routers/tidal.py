import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import User
from auth import get_current_user, get_current_admin
from services import tidal as tidal_svc

router = APIRouter(prefix="/api/tidal", tags=["tidal"])

_user_session_keys: dict = {}


class QualityUpdate(BaseModel):
    quality: str


# ── Auth (admin seulement) ────────────────────────────────────────────────────

@router.post("/auth/start")
async def start_auth(admin: User = Depends(get_current_admin)):
    session_key = str(uuid.uuid4())
    _user_session_keys["admin"] = session_key
    quality = admin.tidal_quality or "LOSSLESS"
    try:
        url, code = await tidal_svc.start_oauth_async(session_key, quality)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur Tidal : {e}")
    return {"session_key": session_key, "url": url, "code": code}


@router.get("/auth/check")
async def check_auth(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    session_key = _user_session_keys.get("admin")
    if not session_key:
        return {"authenticated": False}

    session = await tidal_svc.check_oauth_async(session_key)
    if not session:
        return {"authenticated": False}

    tokens = tidal_svc.session_tokens(session)
    admin.tidal_token_type    = tokens["token_type"]
    admin.tidal_access_token  = tokens["access_token"]
    admin.tidal_refresh_token = tokens["refresh_token"]
    admin.tidal_expiry_time   = tokens["expiry_time"]
    admin.tidal_user_id       = tokens["user_id"]
    db.add(admin)
    await db.commit()

    _user_session_keys.pop("admin", None)
    return {"authenticated": True, "tidal_user_id": tokens["user_id"]}


@router.delete("/unlink")
async def unlink_tidal(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    admin.tidal_user_id       = None
    admin.tidal_token_type    = None
    admin.tidal_access_token  = None
    admin.tidal_refresh_token = None
    admin.tidal_expiry_time   = None
    db.add(admin)
    await db.commit()
    return {"message": "Compte Tidal délié"}


@router.post("/quality")
async def set_quality(
    body: QualityUpdate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    allowed = {"LOW", "HIGH", "LOSSLESS", "HI_RES"}
    if body.quality not in allowed:
        raise HTTPException(status_code=400, detail=f"Qualité invalide : {allowed}")
    admin.tidal_quality = body.quality
    db.add(admin)
    await db.commit()
    return {"quality": body.quality}


# ── Status — visible par tous les utilisateurs connectés ─────────────────────

@router.get("/me")
async def tidal_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne le statut Tidal partagé (compte admin).
    Tous les utilisateurs lisent le compte Tidal de l'admin.
    """
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(User).where(User.is_admin == 1))
    admin = result.scalars().first()
    if not admin:
        return {"connected": False, "quality": "LOSSLESS"}
    return {
        "connected":  bool(admin.tidal_access_token),
        "user_id":    admin.tidal_user_id,
        "quality":    admin.tidal_quality or "LOSSLESS",
        "is_admin":   bool(current_user.is_admin),
    }


# ── Helper — session Tidal partagée depuis le compte admin ───────────────────

async def _get_shared_session(db: AsyncSession):
    """Récupère la session Tidal depuis le compte admin (partagée par tous)."""
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(User).where(User.is_admin == 1))
    admin = result.scalars().first()
    if not admin:
        raise HTTPException(status_code=400, detail="Aucun administrateur configuré")
    session = await tidal_svc.restore_session_async(admin)
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Compte Tidal non connecté. L'administrateur doit le configurer dans Paramètres."
        )
    return session


# ── Search — accessible à tous ────────────────────────────────────────────────

@router.get("/search")
async def search_tidal(
    q: str = Query(..., min_length=1),
    type: str = Query("tracks"),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_shared_session(db)
    return await tidal_svc.search(session, q, search_type=type, limit=limit)


# ── Stream — accessible à tous ────────────────────────────────────────────────

@router.get("/track/{track_id}/stream")
async def get_stream_url(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_shared_session(db)
    try:
        url = await tidal_svc.get_stream_url(session, track_id)
        return {"url": url, "track_id": track_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/artist/{artist_id}/tracks")
async def get_artist_tracks(
    artist_id: int,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_shared_session(db)
    return await tidal_svc.get_artist_top_tracks(session, artist_id, limit=limit)


@router.get("/album/{album_id}/tracks")
async def get_album_tracks(
    album_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_shared_session(db)
    return await tidal_svc.get_album_tracks(session, album_id)
