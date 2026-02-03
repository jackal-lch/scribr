from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text)
    language = Column(String(10), default="en")
    word_count = Column(Integer)
    method = Column(String(20), default="caption")  # "caption", "ai", "whisper-mlx", or "whisper-faster-whisper"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="transcript")
