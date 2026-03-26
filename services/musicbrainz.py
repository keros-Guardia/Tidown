import httpx
import asyncio
from typing import List, Optional

MB_BASE = "https://musicbrainz.org/ws/2/"
HEADERS = {"User-Agent": "MusicApp/1.0.0 (selfhosted@example.com)"}


async def _get(endpoint: str, params: dict) -> dict:
    async with httpx.AsyncClient(headers=HEADERS, timeout=12.0) as client:
        r = await client.get(f"{MB_BASE}{endpoint}", params={"fmt": "json", **params})
        r.raise_for_status()
        return r.json()


# ── Search ────────────────────────────────────────────────────────────────────

async def search_artist(query: str, limit: int = 10) -> List[dict]:
    try:
        data = await _get("artist", {"query": query, "limit": limit})
        return [
            {
                "name": a.get("name"),
                "mbid": a.get("id"),
                "type": a.get("type", ""),
                "country": a.get("country", ""),
                "score": a.get("score"),
                "disambiguation": a.get("disambiguation", ""),
                "source": "musicbrainz",
            }
            for a in data.get("artists", [])
        ]
    except Exception:
        return []


async def search_release(query: str, limit: int = 10) -> List[dict]:
    try:
        data = await _get("release", {"query": query, "limit": limit})
        return [
            {
                "title": r.get("title"),
                "mbid": r.get("id"),
                "date": r.get("date", ""),
                "artist": (r.get("artist-credit") or [{}])[0].get("name", ""),
                "status": r.get("status", ""),
            }
            for r in data.get("releases", [])
        ]
    except Exception:
        return []


# ── Artist releases ───────────────────────────────────────────────────────────

async def get_artist_release_groups(mbid: str, limit: int = 10) -> List[dict]:
    """Fetch the most recent release groups for an artist by MusicBrainz ID."""
    try:
        data = await _get(
            "release-group",
            {"artist": mbid, "type": "album|single|ep", "limit": limit},
        )
        rgs = []
        for rg in data.get("release-groups", []):
            rgs.append(
                {
                    "title": rg.get("title"),
                    "type": rg.get("primary-type", ""),
                    "first_release_date": rg.get("first-release-date", ""),
                    "mbid": rg.get("id"),
                }
            )
        rgs.sort(key=lambda x: x.get("first_release_date") or "", reverse=True)
        return rgs
    except Exception:
        return []


async def get_releases_for_artists(
    artists: List[dict],   # [{"artist_name": ..., "artist_mbid": ..., "artist_image": ...}]
    limit_per_artist: int = 3,
) -> List[dict]:
    """Fetch recent releases for a list of followed artists."""

    async def fetch_one(a: dict) -> List[dict]:
        mbid = a.get("artist_mbid")
        if not mbid:
            return []
        await asyncio.sleep(0.3)  # be polite to MusicBrainz rate limits
        releases = await get_artist_release_groups(mbid, limit=limit_per_artist)
        for r in releases:
            r["artist_name"] = a["artist_name"]
            r["artist_image"] = a.get("artist_image")
        return releases

    results = await asyncio.gather(*[fetch_one(a) for a in artists])
    flat = [r for sublist in results for r in sublist]
    flat.sort(key=lambda x: x.get("first_release_date") or "", reverse=True)
    return flat
