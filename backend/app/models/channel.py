from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import json
from app.database import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    youtube_channel_id = Column(String(255), nullable=False, index=True)
    youtube_channel_name = Column(String(255))
    youtube_channel_url = Column(String(500))
    thumbnail_url = Column(String(500))
    total_videos = Column(Integer)
    tags = Column(Text, default='[]')
    last_checked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('user_id', 'youtube_channel_id', name='uq_user_channel'),)

    user = relationship("User", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

    @property
    def tags_list(self) -> list:
        return json.loads(self.tags) if self.tags else []

    @tags_list.setter
    def tags_list(self, value: list):
        self.tags = json.dumps(value)
