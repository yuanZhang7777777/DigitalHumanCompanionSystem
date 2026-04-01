from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    session_id: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None
    session_id: Optional[str] = None
    preferences: Optional[dict] = None

class UserInDB(UserBase):
    id: str
    created_at: datetime
    last_active: datetime
    preferences: dict = {"theme": "light", "voice_enabled": True}

    class Config:
        arbitrary_types_allowed = True