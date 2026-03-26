from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_db
from models import User, FollowedArtist
from auth import get_current_user
from services.musicbrainz import get_releases_for_artists

router = APIRouter(prefix="/api/feed", tags=["feed"])


@router.get("/releases")
async def get_releases_feed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(3, ge=1, le=10),
):
    """New releases from all followed artists (via MusicBrainz)."""
    result = await db.execute(
        select(FollowedArtist).where(FollowedArtist.user_id == current_user.id)
    )
    followed = result.scalars().all()

    if not followed:
        return []

    artists = [
        {
            "artist_name": f.artist_name,
            "artist_mbid": f.artist_mbid,
            "artist_image": f.artist_image,
        }
        for f in followed
        if f.artist_mbid  # Only artists with MusicBrainz ID can have releases fetched
    ]

    releases = await get_releases_for_artists(artists, limit_per_artist=limit)
    return releases
