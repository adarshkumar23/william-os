from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.core.database import Base

class GoogleToken(Base):
    __tablename__ = "google_tokens"
    __table_args__ = {"schema": "calendar"}
    id = Column(Integer, primary_key=True)
    user_id = Column(Text, nullable=False, unique=True)
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expiry = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class AppleCredential(Base):
    __tablename__ = "apple_credentials"
    __table_args__ = {"schema": "calendar"}
    id = Column(Integer, primary_key=True)
    user_id = Column(Text, nullable=False, unique=True)
    apple_id_encrypted = Column(Text)
    app_password_encrypted = Column(Text)
    caldav_url = Column(Text, default="https://caldav.icloud.com")
    created_at = Column(DateTime, default=datetime.utcnow)

class CachedEvent(Base):
    __tablename__ = "cached_events"
    __table_args__ = {"schema": "calendar"}
    id = Column(Integer, primary_key=True)
    user_id = Column(Text, nullable=False)
    source = Column(String(10))
    event_id = Column(Text)
    title = Column(Text)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    location = Column(Text)
    description = Column(Text)
    last_synced = Column(DateTime, default=datetime.utcnow)
