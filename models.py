from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    # Rôle
    is_admin = Column(Integer, default=0, nullable=False)  # 1 = admin

    # Last.fm
    lastfm_username   = Column(String, nullable=True)
    lastfm_api_key    = Column(String, nullable=True)   # chiffré
    lastfm_api_secret = Column(String, nullable=True)   # chiffré

    # Tidal
    tidal_user_id       = Column(String, nullable=True)
    tidal_token_type    = Column(String, nullable=True)
    tidal_access_token  = Column(String, nullable=True)  # chiffré
    tidal_refresh_token = Column(String, nullable=True)  # chiffré
    tidal_expiry_time   = Column(DateTime, nullable=True)
    tidal_quality       = Column(String, nullable=True, default="LOSSLESS")

    created_at = Column(DateTime, default=datetime.utcnow)

    followed_artists = relationship(
        "FollowedArtist", back_populates="user", cascade="all, delete-orphan"
    )


class FollowedArtist(Base):
    __tablename__ = "followed_artists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    artist_mbid = Column(String, nullable=True)
    artist_name = Column(String, nullable=False)
    artist_lastfm_url = Column(String, nullable=True)
    artist_image = Column(String, nullable=True)
    followed_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="followed_artists")

    __table_args__ = (UniqueConstraint("user_id", "artist_name", name="uq_user_artist"),)
