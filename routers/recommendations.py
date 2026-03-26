import asyncio
import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, FollowedArtist
from auth import get_current_user
from crypto import decrypt
from services.lastfm import (
    get_similar_artists,
    get_similar_tracks,
    get_artist_top_tracks,
    get_user_top_tracks,
)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


def _check_key(user: User) -> str:
    if not user.lastfm_api_key:
        raise HTTPException(
            status_code=400,
            detail="Clé API Last.fm non configurée. Rendez-vous dans Paramètres → Last.fm."
        )
    return decrypt(user.lastfm_api_key)


@router.get("/artists")
async def get_recommended_artists(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    api_key = _check_key(current_user)

    result = await db.execute(
        select(FollowedArtist).where(FollowedArtist.user_id == current_user.id)
    )
    followed = result.scalars().all()
    if not followed:
        return []

    followed_names = {f.artist_name.lower() for f in followed}
    seeds = random.sample(followed, min(5, len(followed)))

    async def fetch_similar(artist: FollowedArtist):
        similar = await get_similar_artists(artist.artist_name, api_key=api_key, limit=8)
        for s in similar:
            s["reason"] = f"Similaire à {artist.artist_name}"
        return similar

    results = await asyncio.gather(*[fetch_similar(a) for a in seeds])
    seen, recommendations = set(), []
    for group in results:
        for artist in group:
            name = artist.get("name", "").lower()
            if name and name not in followed_names and name not in seen:
                seen.add(name)
                recommendations.append(artist)

    recommendations.sort(key=lambda x: float(x.get("match") or 0), reverse=True)
    return recommendations[:20]


@router.get("/tracks")
async def get_recommended_tracks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Recommandations de morceaux basées sur :
    1. Les top tracks des artistes suivis (seed tracks)
    2. Les morceaux similaires via track.getSimilar
    3. Si Last.fm lié : les top tracks personnels de l'utilisateur comme seeds supplémentaires
    """
    api_key = _check_key(current_user)

    result = await db.execute(
        select(FollowedArtist).where(FollowedArtist.user_id == current_user.id)
    )
    followed = result.scalars().all()
    if not followed:
        return []

    # ── Étape 1 : récupérer les top tracks de 4 artistes suivis aléatoires ──
    seeds_artists = random.sample(followed, min(4, len(followed)))

    async def artist_top(a: FollowedArtist):
        tracks = await get_artist_top_tracks(a.artist_name, api_key=api_key, limit=3)
        return [(t["name"], a.artist_name) for t in tracks if t.get("name")]

    artist_track_groups = await asyncio.gather(*[artist_top(a) for a in seeds_artists])
    seed_tracks = [t for group in artist_track_groups for t in group]

    # ── Étape 2 : si Last.fm lié, ajouter les top tracks perso comme seeds ──
    if current_user.lastfm_username:
        try:
            user_tops = await get_user_top_tracks(
                current_user.lastfm_username, api_key=api_key, period="1month", limit=5
            )
            for t in user_tops:
                if t.get("name") and t.get("artist"):
                    seed_tracks.append((t["name"], t["artist"]))
        except Exception:
            pass

    if not seed_tracks:
        return []

    # ── Étape 3 : récupérer les similaires pour chaque seed ──
    seeds_sample = random.sample(seed_tracks, min(6, len(seed_tracks)))

    async def fetch_similar_tracks(track_name: str, artist_name: str):
        similar = await get_similar_tracks(
            track_name, artist_name, api_key=api_key, limit=6
        )
        for s in similar:
            s["reason"] = f"Similaire à {track_name}"
            if not s.get("image"):
                s["image"] = None
        return similar

    sim_results = await asyncio.gather(*[
        fetch_similar_tracks(name, artist) for name, artist in seeds_sample
    ])

    # ── Étape 4 : dédupliquer et scorer ──
    seen, recommendations = set(), []
    followed_artist_names = {f.artist_name.lower() for f in followed}

    for group in sim_results:
        for track in group:
            tname  = (track.get("name") or "").strip()
            tartist = (track.get("artist") or "").strip()
            key = f"{tname.lower()}||{tartist.lower()}"
            if tname and tartist and key not in seen:
                seen.add(key)
                recommendations.append(track)

    recommendations.sort(key=lambda x: float(x.get("match") or 0), reverse=True)
    return recommendations[:30]
