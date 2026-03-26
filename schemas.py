from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    lastfm_username: Optional[str] = None
    has_lastfm_api_key: bool = False
    is_admin: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


# ── Last.fm ───────────────────────────────────────────────────────────────────

class LinkLastfm(BaseModel):
    lastfm_username: str
    lastfm_api_key: str
    lastfm_api_secret: str


# ── Artists ───────────────────────────────────────────────────────────────────

class ArtistFollow(BaseModel):
    artist_name: str
    artist_mbid: Optional[str] = None
    artist_lastfm_url: Optional[str] = None
    artist_image: Optional[str] = None


class FollowedArtistOut(BaseModel):
    id: int
    artist_name: str
    artist_mbid: Optional[str]
    artist_lastfm_url: Optional[str]
    artist_image: Optional[str]
    followed_at: datetime

    class Config:
        from_attributes = True


# ── Search ────────────────────────────────────────────────────────────────────

class ArtistResult(BaseModel):
    name: str
    mbid: Optional[str]
    listeners: Optional[str] = None
    url: Optional[str] = None
    image: Optional[str] = None
    source: str = "lastfm"


class TrackResult(BaseModel):
    name: str
    artist: str
    url: Optional[str] = None
    image: Optional[str] = None
    listeners: Optional[str] = None


class ReleaseResult(BaseModel):
    title: str
    mbid: Optional[str]
    date: Optional[str] = None
    artist: Optional[str] = None


# ── Feed ─────────────────────────────────────────────────────────────────────

class ReleaseEntry(BaseModel):
    artist_name: str
    artist_image: Optional[str]
    title: str
    type: Optional[str]
    first_release_date: Optional[str]
    mbid: Optional[str]


# ── Recommendations ───────────────────────────────────────────────────────────

class RecommendedArtist(BaseModel):
    name: str
    match: Optional[str] = None
    url: Optional[str] = None
    mbid: Optional[str] = None
    image: Optional[str] = None
    reason: Optional[str] = None


class ChangePassword(BaseModel):
    current_password: str
    new_password: str
