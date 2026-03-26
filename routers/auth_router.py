from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_db
from models import User
from schemas import UserCreate, UserOut, Token, LinkLastfm, ChangePassword
from auth import get_password_hash, verify_password, create_access_token, get_current_user
from crypto import encrypt, decrypt

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_to_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "lastfm_username": user.lastfm_username,
        "has_lastfm_api_key": bool(user.lastfm_api_key),
        "is_admin": bool(user.is_admin),
        "created_at": user.created_at,
    }


@router.get("/setup-needed")
async def setup_needed(db: AsyncSession = Depends(get_db)):
    """Retourne true si aucun utilisateur n'existe — affiche le formulaire de création admin."""
    result = await db.execute(select(func.count()).select_from(User))
    count = result.scalar()
    return {"setup_needed": count == 0}


@router.post("/register", response_model=UserOut)
async def register(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    - Si aucun utilisateur n'existe → crée l'admin (accessible sans token).
    - Sinon → bloqué (seul l'admin peut créer des comptes via /api/admin/users).
    """
    result = await db.execute(select(func.count()).select_from(User))
    count = result.scalar()

    if count > 0:
        raise HTTPException(
            status_code=403,
            detail="Inscription publique désactivée. Contactez l'administrateur."
        )

    # Vérifier unicité
    existing = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Nom d'utilisateur ou email déjà utilisé")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=get_password_hash(body.password),
        is_admin=1,  # Premier utilisateur = admin
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _user_to_out(user)


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return _user_to_out(current_user)


@router.post("/link-lastfm", response_model=UserOut)
async def link_lastfm(
    body: LinkLastfm,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from services.lastfm import validate_user
    valid = await validate_user(body.lastfm_username, api_key=body.lastfm_api_key)
    if not valid:
        raise HTTPException(status_code=400, detail="Utilisateur Last.fm introuvable ou clé API invalide.")

    current_user.lastfm_username  = body.lastfm_username
    current_user.lastfm_api_key   = encrypt(body.lastfm_api_key)
    current_user.lastfm_api_secret = encrypt(body.lastfm_api_secret) if body.lastfm_api_secret else None
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return _user_to_out(current_user)


@router.delete("/unlink-lastfm", response_model=UserOut)
async def unlink_lastfm(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.lastfm_username   = None
    current_user.lastfm_api_key    = None
    current_user.lastfm_api_secret = None
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return _user_to_out(current_user)


@router.post("/change-password", response_model=UserOut)
async def change_password(
    body: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit faire au moins 8 caractères")

    current_user.hashed_password = get_password_hash(body.new_password)
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return _user_to_out(current_user)
