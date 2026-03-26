"""
Wrapper autour de tidalapi.
Chaque utilisateur a sa propre session OAuth stockée (chiffrée) en base.
"""
import asyncio
import tidalapi
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from crypto import encrypt, decrypt

_executor = ThreadPoolExecutor(max_workers=4)

# Sessions OAuth en attente d'authentification {session_id: (session, future)}
_pending: dict = {}


def _run_sync(fn, *args):
    """Exécute une fonction tidalapi (synchrone) dans un thread pour ne pas bloquer asyncio."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(_executor, fn, *args)


# ── Session ───────────────────────────────────────────────────────────────────

def _get_quality(quality_str: str):
    """
    Retourne l'objet Quality correspondant.
    tidalapi a changé les noms entre versions — on teste les deux.
    """
    q = tidalapi.Quality

    # Mapping avec fallbacks pour différentes versions de tidalapi
    candidates = {
        "LOW":      ["low_320k", "low_96k", "LOW_320k", "low"],
        "HIGH":     ["high_320k", "high", "HIGH_320k"],
        "LOSSLESS": ["lossless", "LOSSLESS", "high_lossless"],
        "HI_RES":   ["hi_res_lossless", "hi_res", "HI_RES_LOSSLESS", "master"],
    }

    for attr in candidates.get(quality_str, ["lossless"]):
        if hasattr(q, attr):
            return getattr(q, attr)

    # Fallback absolu : première valeur disponible de l'enum
    return list(q)[0]


def build_session(quality: str = "LOSSLESS") -> tidalapi.Session:
    config = tidalapi.Config(quality=_get_quality(quality))
    return tidalapi.Session(config)


def _restore_session_sync(user) -> Optional[tidalapi.Session]:
    """Recrée une session Tidal depuis les tokens stockés en base (synchrone)."""
    if not user.tidal_access_token:
        return None
    try:
        session = build_session(user.tidal_quality or "LOSSLESS")
        expiry = user.tidal_expiry_time
        session.load_oauth_session(
            token_type=user.tidal_token_type or "Bearer",
            access_token=decrypt(user.tidal_access_token),
            refresh_token=decrypt(user.tidal_refresh_token) if user.tidal_refresh_token else None,
            expiry_time=expiry,
        )
        # Ne pas utiliser session.check_login() car il requiert un user_id valide,
        # or l'API Tidal bloque souvent le Endpoint GET /v1/sessions désormais.
        return session if session.access_token else None
    except Exception as e:
        print(f"[TIDAL RESTORE DEBUG] Erreur lors de la restauration : {e}")
        return None


def restore_session(user) -> Optional[tidalapi.Session]:
    """Version synchrone pour compatibilité — ne pas appeler depuis async."""
    return _restore_session_sync(user)


async def restore_session_async(user) -> Optional[tidalapi.Session]:
    """Recrée une session Tidal de façon non-bloquante (pour les routes async)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _restore_session_sync, user)


# ── OAuth flow ────────────────────────────────────────────────────────────────

def _start_oauth_sync(session_key: str, quality: str = "LOSSLESS"):
    """
    Démarre le flux OAuth device-code (synchrone, à exécuter dans un thread).
    Retourne (url, code) — l'utilisateur ouvre l'URL sur tidal.com.

    IMPORTANT : tidalapi crée un ThreadPoolExecutor local dans login_oauth().
    Si on ne garde pas de référence à la future, l'executor peut être GC'd,
    interrompant le thread de polling OAuth avant que l'utilisateur autorise.
    On stocke donc (session, future) dans _pending pour maintenir la référence.
    """
    session = build_session(quality)
    login_info, future = session.login_oauth()
    # La référence à future empêche le GC de l'executor interne de tidalapi
    _pending[session_key] = (session, future)
    return login_info.verification_uri_complete, login_info.user_code


def start_oauth(session_key: str, quality: str = "LOSSLESS"):
    """Version synchrone pour compatibilité."""
    return _start_oauth_sync(session_key, quality)


async def start_oauth_async(session_key: str, quality: str = "LOSSLESS"):
    """Démarre le flux OAuth de façon non-bloquante (pour les routes async)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _start_oauth_sync, session_key, quality)


def _check_oauth_sync(session_key: str) -> Optional[tidalapi.Session]:
    """
    Vérifie si l'utilisateur a autorisé la session (synchrone, à exécuter dans un thread).
    Utilise future.result(timeout=0) pour vérifier sans bloquer.
    Retourne la session si authentifiée, None sinon.
    """
    import concurrent.futures as cf
    import traceback
    entry = _pending.get(session_key)
    if not entry:
        return None
    session, future = entry

    try:
        # timeout=0 : non-bloquant, lève TimeoutError si pas encore terminée
        future.result(timeout=0)
    except cf.TimeoutError:
        # L'utilisateur n'a pas encore autorisé
        return None
    except Exception as e:
        # La future s'est terminée par une erreur OAuth locale (ex: GET /v1/sessions 401)
        # Mais très souvent, tidalapi a DEJA enregistré les tokens avant de faire cet appel !
        if getattr(session, 'access_token', None):
            print(f"[TIDAL OAUTH DEBUG] Contournement du bug tidalapi ! Les tokens sont là malgré l'erreur : {e}")
            _pending.pop(session_key, None)
            return session

        print(f"[TIDAL OAUTH DEBUG] Exception during future.result() : {e}")
        traceback.print_exc()
        _pending.pop(session_key, None)
        return None

    # Succès : process_link_login a déjà configuré les tokens dans session
    print("[TIDAL OAUTH DEBUG] Future successful -> tokens acquired.")
    _pending.pop(session_key, None)
    return session


def check_oauth(session_key: str) -> Optional[tidalapi.Session]:
    """Version synchrone — ne pas appeler depuis async."""
    return _check_oauth_sync(session_key)


async def check_oauth_async(session_key: str) -> Optional[tidalapi.Session]:
    """Vérifie l'autorisation OAuth de façon non-bloquante (pour les routes async)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _check_oauth_sync, session_key)


def session_tokens(session: tidalapi.Session) -> dict:
    """Extrait les tokens d'une session pour stockage."""
    return {
        "token_type":    session.token_type or "Bearer",
        "access_token":  encrypt(session.access_token),
        "refresh_token": encrypt(session.refresh_token) if session.refresh_token else None,
        "expiry_time":   session.expiry_time,
        "user_id":       str(session.user.id) if session.user else None,
    }


# ── Search ────────────────────────────────────────────────────────────────────

def _serialize_track(t) -> dict:
    try:
        artist_name = t.artist.name if t.artist else ""
        album_name  = t.album.name  if t.album  else ""
        cover = None
        if t.album and hasattr(t.album, 'image'):
            try: cover = t.album.image(320)
            except Exception: pass
        return {
            "id":       t.id,
            "name":     t.name,
            "artist":   artist_name,
            "album":    album_name,
            "duration": t.duration,
            "image":    cover,
            "explicit": getattr(t, 'explicit', False),
            "source":   "tidal",
        }
    except Exception:
        return {}


def _serialize_artist(a) -> dict:
    try:
        cover = None
        try: cover = a.image(320)
        except Exception: pass
        return {
            "id":     a.id,
            "name":   a.name,
            "image":  cover,
            "source": "tidal",
        }
    except Exception:
        return {}


def _serialize_album(a) -> dict:
    try:
        cover = None
        try: cover = a.image(320)
        except Exception: pass
        return {
            "id":           a.id,
            "name":         a.name,
            "artist":       a.artist.name if a.artist else "",
            "release_date": str(a.release_date) if getattr(a, 'release_date', None) else None,
            "image":        cover,
            "num_tracks":   getattr(a, 'num_tracks', None),
            "source":       "tidal",
        }
    except Exception:
        return {}


def _do_search(session: tidalapi.Session, query: str, search_type: str, limit: int):
    if search_type == "tracks":
        results = session.search(query, models=[tidalapi.Track], limit=limit)
        return [_serialize_track(t) for t in results.get("tracks", []) if t]
    elif search_type == "artists":
        results = session.search(query, models=[tidalapi.Artist], limit=limit)
        return [_serialize_artist(a) for a in results.get("artists", []) if a]
    elif search_type == "albums":
        results = session.search(query, models=[tidalapi.Album], limit=limit)
        return [_serialize_album(a) for a in results.get("albums", []) if a]
    return []


async def search(session: tidalapi.Session, query: str, search_type: str = "tracks", limit: int = 20):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _do_search, session, query, search_type, limit)


# ── Stream URL ────────────────────────────────────────────────────────────────

def _get_stream_url(session: tidalapi.Session, track_id: int) -> Optional[str]:
    try:
        track = session.track(track_id)
        url = track.get_url()
        return url
    except Exception as e:
        raise ValueError(f"Impossible d'obtenir l'URL du stream : {e}")


async def get_stream_url(session: tidalapi.Session, track_id: int) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _get_stream_url, session, track_id)


# ── Artist top tracks ─────────────────────────────────────────────────────────

def _get_artist_top_tracks(session: tidalapi.Session, artist_id: int, limit: int = 10):
    try:
        artist = session.artist(artist_id)
        tracks = artist.get_top_tracks(limit=limit)
        return [_serialize_track(t) for t in tracks if t]
    except Exception:
        return []


async def get_artist_top_tracks(session: tidalapi.Session, artist_id: int, limit: int = 10):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _get_artist_top_tracks, session, artist_id, limit)


# ── Album tracks ──────────────────────────────────────────────────────────────

def _get_album_tracks(session: tidalapi.Session, album_id: int):
    try:
        album = session.album(album_id)
        tracks = album.tracks()
        return [_serialize_track(t) for t in tracks if t]
    except Exception:
        return []


async def get_album_tracks(session: tidalapi.Session, album_id: int):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _get_album_tracks, session, album_id)
