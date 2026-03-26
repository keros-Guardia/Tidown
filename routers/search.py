from fastapi import APIRouter, Query, Depends, HTTPException
import asyncio

from auth import get_current_user
from models import User
from crypto import decrypt
from services import lastfm as lfm
from services import musicbrainz as mb

router = APIRouter(prefix="/api/search", tags=["search"])


def _get_api_key(user: User) -> str:
    if not user.lastfm_api_key:
        raise HTTPException(
            status_code=400,
            detail="Clé API Last.fm non configurée. Rendez-vous dans Paramètres → Last.fm."
        )
    return decrypt(user.lastfm_api_key)


@router.get("/artists")
async def search_artists(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
):
    api_key = _get_api_key(current_user)
    lfm_results, mb_results = await asyncio.gather(
        lfm.search_artist(q, api_key=api_key, limit=8),
        mb.search_artist(q, limit=5),
    )
    mb_map = {r["name"].lower(): r for r in mb_results}
    seen = set()
    merged = []
    for a in lfm_results:
        key = a["name"].lower()
        seen.add(key)
        if not a.get("mbid") and key in mb_map:
            a["mbid"] = mb_map[key].get("mbid")
        merged.append(a)
    for r in mb_results:
        if r["name"].lower() not in seen:
            merged.append(r)
    return merged


@router.get("/tracks")
async def search_tracks(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
):
    api_key = _get_api_key(current_user)
    return await lfm.search_track(q, api_key=api_key, limit=15)


@router.get("/releases")
async def search_releases(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
):
    # MusicBrainz ne nécessite pas de clé API
    return await mb.search_release(q, limit=10)


@router.get("/artist/{name}")
async def get_artist_detail(
    name: str,
    current_user: User = Depends(get_current_user),
):
    api_key = _get_api_key(current_user)
    info = await lfm.get_artist_info(name, api_key=api_key)
    if not info:
        return {"error": "Artiste introuvable"}
    top_tracks = await lfm.get_artist_top_tracks(name, api_key=api_key, limit=5)
    info["top_tracks"] = top_tracks
    return info
