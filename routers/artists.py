from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_db
from models import User, FollowedArtist
from schemas import ArtistFollow, FollowedArtistOut
from auth import get_current_user
from crypto import decrypt
from services.lastfm import get_user_top_artists

router = APIRouter(prefix="/api/artists", tags=["artists"])


@router.get("/following", response_model=List[FollowedArtistOut])
async def get_following(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FollowedArtist)
        .where(FollowedArtist.user_id == current_user.id)
        .order_by(FollowedArtist.followed_at.desc())
    )
    return result.scalars().all()


@router.post("/follow", response_model=FollowedArtistOut)
async def follow_artist(
    body: ArtistFollow,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FollowedArtist).where(
            FollowedArtist.user_id == current_user.id,
            FollowedArtist.artist_name == body.artist_name,
        )
    )
    if (existing := result.scalar_one_or_none()):
        return existing

    artist = FollowedArtist(
        user_id=current_user.id,
        artist_name=body.artist_name,
        artist_mbid=body.artist_mbid,
        artist_lastfm_url=body.artist_lastfm_url,
        artist_image=body.artist_image,
    )
    db.add(artist)
    await db.commit()
    await db.refresh(artist)
    return artist


@router.delete("/unfollow/{artist_name}")
async def unfollow_artist(
    artist_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FollowedArtist).where(
            FollowedArtist.user_id == current_user.id,
            FollowedArtist.artist_name == artist_name,
        )
    )
    artist = result.scalar_one_or_none()
    if not artist:
        raise HTTPException(status_code=404, detail="Artiste non suivi")
    await db.delete(artist)
    await db.commit()
    return {"message": f"Désabonné de {artist_name}"}


@router.post("/import-lastfm")
async def import_from_lastfm(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.lastfm_username:
        raise HTTPException(status_code=400, detail="Aucun compte Last.fm lié")
    if not current_user.lastfm_api_key:
        raise HTTPException(status_code=400, detail="Clé API Last.fm non configurée")

    top_artists = await get_user_top_artists(
        current_user.lastfm_username,
        api_key=decrypt(current_user.lastfm_api_key),
        period="6month",
        limit=20,
    )
    added = 0
    for a in top_artists:
        result = await db.execute(
            select(FollowedArtist).where(
                FollowedArtist.user_id == current_user.id,
                FollowedArtist.artist_name == a["name"],
            )
        )
        if not result.scalar_one_or_none():
            db.add(FollowedArtist(
                user_id=current_user.id,
                artist_name=a["name"],
                artist_mbid=a.get("mbid"),
                artist_lastfm_url=a.get("url"),
                artist_image=a.get("image"),
            ))
            added += 1
    await db.commit()
    return {"imported": added, "total": len(top_artists)}
