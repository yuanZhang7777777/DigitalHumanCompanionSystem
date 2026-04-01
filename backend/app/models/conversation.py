from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class Message(BaseModel):
    role: str  # 'user' 或 'assistant'
    content: str
    timestamp: datetime
    emotion: Optional[str] = None

class ConversationBase(BaseModel):
    user_id: str
    digital_person_id: str
    messages: List[Message] = []
    context_summary: Optional[str] = None

class ConversationCreate(ConversationBase):
    pass

class ConversationUpdate(BaseModel):
    messages: Optional[List[Message]] = None
    context_summary: Optional[str] = None

class ConversationInDB(ConversationBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        arbitrary_types_allowed = True