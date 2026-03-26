import httpx
from typing import List, Optional

LASTFM_BASE = "https://ws.audioscrobbler.com/2.0/"


def _require_key(api_key: Optional[str]) -> str:
    if not api_key:
        raise ValueError("Clé API Last.fm non configurée. Rendez-vous dans Paramètres pour la renseigner.")
    return api_key


async def _get(method: str, params: dict, api_key: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            LASTFM_BASE,
            params={"method": method, "api_key": api_key, "format": "json", **params},
        )
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise ValueError(data.get("message", "Erreur Last.fm"))
        return data


def _pick_image(images: list, size: str = "large") -> Optional[str]:
    for img in images:
        if img.get("size") == size and img.get("#text"):
            return img["#text"]
    return None


# ── Search ────────────────────────────────────────────────────────────────────

async def search_artist(query: str, api_key: str, limit: int = 10) -> List[dict]:
    key = _require_key(api_key)
    try:
        data = await _get("artist.search", {"artist": query, "limit": limit}, key)
        artists = data.get("results", {}).get("artistmatches", {}).get("artist", [])
        return [
            {
                "name": a.get("name"),
                "listeners": a.get("listeners"),
                "mbid": a.get("mbid") or None,
                "url": a.get("url"),
                "image": _pick_image(a.get("image", [])),
                "source": "lastfm",
            }
            for a in artists
        ]
    except ValueError:
        raise
    except Exception:
        return []


async def search_track(query: str, api_key: str, limit: int = 10) -> List[dict]:
    key = _require_key(api_key)
    try:
        data = await _get("track.search", {"track": query, "limit": limit}, key)
        tracks = data.get("results", {}).get("trackmatches", {}).get("track", [])
        return [
            {
                "name": t.get("name"),
                "artist": t.get("artist"),
                "url": t.get("url"),
                "image": _pick_image(t.get("image", [])),
                "listeners": t.get("listeners"),
            }
            for t in tracks
        ]
    except ValueError:
        raise
    except Exception:
        return []


# ── Artist info ───────────────────────────────────────────────────────────────

async def get_artist_info(artist_name: str, api_key: str) -> Optional[dict]:
    key = _require_key(api_key)
    try:
        data = await _get("artist.getInfo", {"artist": artist_name}, key)
        a = data.get("artist", {})
        return {
            "name": a.get("name"),
            "url": a.get("url"),
            "mbid": a.get("mbid") or None,
            "listeners": a.get("stats", {}).get("listeners"),
            "playcount": a.get("stats", {}).get("playcount"),
            "bio": (a.get("bio", {}).get("summary") or "")[:600],
            "tags": [t["name"] for t in a.get("tags", {}).get("tag", [])],
            "similar": [s["name"] for s in a.get("similar", {}).get("artist", [])],
            "image": _pick_image(a.get("image", []), "extralarge")
                     or _pick_image(a.get("image", []), "large"),
        }
    except ValueError:
        raise
    except Exception:
        return None


async def get_similar_artists(artist_name: str, api_key: str, limit: int = 8) -> List[dict]:
    key = _require_key(api_key)
    try:
        data = await _get("artist.getSimilar", {"artist": artist_name, "limit": limit}, key)
        return [
            {
                "name": a.get("name"),
                "match": a.get("match"),
                "url": a.get("url"),
                "mbid": a.get("mbid") or None,
                "image": _pick_image(a.get("image", [])),
            }
            for a in data.get("similarartists", {}).get("artist", [])
        ]
    except ValueError:
        raise
    except Exception:
        return []


async def get_artist_top_tracks(artist_name: str, api_key: str, limit: int = 5) -> List[dict]:
    key = _require_key(api_key)
    try:
        data = await _get("artist.getTopTracks", {"artist": artist_name, "limit": limit}, key)
        return [
            {
                "name": t.get("name"),
                "playcount": t.get("playcount"),
                "url": t.get("url"),
            }
            for t in data.get("toptracks", {}).get("track", [])
        ]
    except ValueError:
        raise
    except Exception:
        return []


# ── User ──────────────────────────────────────────────────────────────────────

async def validate_user(lastfm_username: str, api_key: str) -> bool:
    key = _require_key(api_key)
    try:
        await _get("user.getInfo", {"user": lastfm_username}, key)
        return True
    except Exception:
        return False


async def get_user_top_artists(lastfm_username: str, api_key: str, period: str = "6month", limit: int = 30) -> List[dict]:
    key = _require_key(api_key)
    try:
        data = await _get("user.getTopArtists", {
            "user": lastfm_username,
            "period": period,
            "limit": limit,
        }, key)
        return [
            {
                "name": a.get("name"),
                "playcount": a.get("playcount"),
                "mbid": a.get("mbid") or None,
                "url": a.get("url"),
                "image": _pick_image(a.get("image", [])),
            }
            for a in data.get("topartists", {}).get("artist", [])
        ]
    except ValueError:
        raise
    except Exception:
        return []


async def get_similar_tracks(track_name: str, artist_name: str, api_key: str, limit: int = 8) -> List[dict]:
    """Récupère les morceaux similaires via Last.fm track.getSimilar."""
    key = _require_key(api_key)
    try:
        data = await _get("track.getSimilar", {
            "track": track_name,
            "artist": artist_name,
            "limit": limit,
            "autocorrect": 1,
        }, key)
        return [
            {
                "name": t.get("name"),
                "artist": t.get("artist", {}).get("name") if isinstance(t.get("artist"), dict) else t.get("artist"),
                "match": t.get("match"),
                "url": t.get("url"),
                "image": _pick_image(t.get("image", [])),
                "playcount": t.get("playcount"),
            }
            for t in data.get("similartracks", {}).get("track", [])
        ]
    except ValueError:
        raise
    except Exception:
        return []


async def get_track_info(track_name: str, artist_name: str, api_key: str) -> Optional[dict]:
    """Infos détaillées sur un morceau."""
    key = _require_key(api_key)
    try:
        data = await _get("track.getInfo", {
            "track": track_name,
            "artist": artist_name,
            "autocorrect": 1,
        }, key)
        t = data.get("track", {})
        return {
            "name": t.get("name"),
            "artist": t.get("artist", {}).get("name") if isinstance(t.get("artist"), dict) else "",
            "url": t.get("url"),
            "duration": t.get("duration"),
            "playcount": t.get("playcount"),
            "listeners": t.get("listeners"),
            "image": _pick_image(t.get("album", {}).get("image", []), "extralarge")
                     or _pick_image(t.get("album", {}).get("image", []), "large"),
            "album": t.get("album", {}).get("title"),
            "tags": [tg["name"] for tg in t.get("toptags", {}).get("tag", [])],
        }
    except Exception:
        return None


async def get_user_top_tracks(lastfm_username: str, api_key: str, period: str = "1month", limit: int = 10) -> List[dict]:
    """Top morceaux écoutés par l'utilisateur."""
    key = _require_key(api_key)
    try:
        data = await _get("user.getTopTracks", {
            "user": lastfm_username,
            "period": period,
            "limit": limit,
        }, key)
        return [
            {
                "name": t.get("name"),
                "artist": t.get("artist", {}).get("name") if isinstance(t.get("artist"), dict) else "",
                "playcount": t.get("playcount"),
                "url": t.get("url"),
                "image": _pick_image(t.get("image", [])),
            }
            for t in data.get("toptracks", {}).get("track", [])
        ]
    except Exception:
        return []
