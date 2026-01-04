from sqlalchemy import Column, String, Text, DateTime, Integer, BigInteger, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    youtube_video_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    published_at = Column(DateTime(timezone=True), index=True)
    duration_seconds = Column(Integer)
    thumbnail_url = Column(String(500))

    # Engagement stats
    view_count = Column(BigInteger)
    like_count = Column(BigInteger)
    comment_count = Column(BigInteger)

    # Additional metadata
    tags = Column(ARRAY(String), default=[], server_default='{}')
    category_id = Column(String(10))  # YouTube category ID
    definition = Column(String(10))  # hd, sd
    caption = Column(Boolean)  # Has YouTube captions available
    default_language = Column(String(20))
    default_audio_language = Column(String(20))

    # Transcript status
    has_transcript = Column(Boolean, default=False)
    transcript_status = Column(String(20), default="pending")  # pending, extracting, completed, failed
    transcript_error = Column(String(500))  # Error message if extraction failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    channel = relationship("Channel", back_populates="videos")
    transcript = relationship("Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan")
