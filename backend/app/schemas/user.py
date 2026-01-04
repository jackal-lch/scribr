from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    google_id: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserInDB(UserResponse):
    google_id: str
    updated_at: datetime


class TelegramConfig(BaseModel):
    bot_token: str
    chat_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
