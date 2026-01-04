from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    youtube_channel_id = Column(String(255), nullable=False, index=True)
    youtube_channel_name = Column(String(255))
    youtube_channel_url = Column(String(500))
    thumbnail_url = Column(String(500))
    total_videos = Column(Integer)
    tags = Column(ARRAY(String), default=[], server_default='{}')
    last_checked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('user_id', 'youtube_channel_id', name='uq_user_channel'),)

    user = relationship("User", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")
