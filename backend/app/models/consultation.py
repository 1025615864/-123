"""咨询记录模型"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class Consultation(Base):
    """咨询会话表"""
    __tablename__ = "consultations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    messages = relationship("ChatMessage", back_populates="consultation", cascade="all, delete-orphan")


class ChatMessage(Base):
    """对话消息表"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    consultation_id = Column(Integer, ForeignKey("consultations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user/assistant
    content = Column(Text, nullable=False)
    references = Column(Text, nullable=True)  # JSON格式存储引用的法条
    rating = Column(Integer, nullable=True)  # 1=差评, 2=一般, 3=好评
    feedback = Column(Text, nullable=True)  # 用户反馈
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    consultation = relationship("Consultation", back_populates="messages")
