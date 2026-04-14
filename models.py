from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from database import Base

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    role = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class AISettings(Base):
    __tablename__ = "ai_settings"

    id = Column(Integer, primary_key=True, index=True)
    system_prompt = Column(Text, default="You are a professional English sales assistant.")