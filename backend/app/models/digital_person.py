from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DigitalPersonBase(BaseModel):
    user_id: str
    name: str
    relationship: str
    personality: str
    avatar: Optional[str] = None
    speaking_video_url: Optional[str] = None
    last_avatar_for_video: Optional[str] = None  # 新增：记录生成视频时使用的头像，用于判断是否需要更新
    custom_prompt: Optional[str] = None

class DigitalPersonCreate(DigitalPersonBase):
    pass

class DigitalPersonUpdate(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    personality: Optional[str] = None
    avatar: Optional[str] = None
    speaking_video_url: Optional[str] = None
    last_avatar_for_video: Optional[str] = None
    custom_prompt: Optional[str] = None

class DigitalPersonInDB(DigitalPersonBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        arbitrary_types_allowed = True