"""数据模型"""
from .user import User
from .consultation import Consultation, ChatMessage
from .forum import Post, Comment, PostLike, CommentLike, PostFavorite, PostReaction
from .news import News, NewsFavorite, NewsViewHistory, NewsSubscription
from .news_ai import NewsAIAnnotation
from .news_workbench import NewsVersion, NewsAIGeneration, NewsLinkCheck
from .lawfirm import LawFirm, Lawyer, LawyerConsultation, LawyerConsultationMessage, LawyerReview
from .knowledge import LegalKnowledge, ConsultationTemplate
from .notification import Notification
from .system import SystemConfig, AdminLog
from .calendar import CalendarReminder

__all__ = [
    "User", 
    "Consultation", 
    "ChatMessage",
    "Post",
    "Comment", 
    "PostLike",
    "CommentLike",
    "PostFavorite",
    "News",
    "NewsFavorite",
    "NewsViewHistory",
    "NewsSubscription",
    "NewsAIAnnotation",
    "NewsVersion",
    "NewsAIGeneration",
    "NewsLinkCheck",
    "LawFirm",
    "Lawyer",
    "LawyerConsultation",
    "LawyerConsultationMessage",
    "LawyerReview",
    "LegalKnowledge",
    "ConsultationTemplate",
    "PostReaction",
    "Notification",
    "SystemConfig",
    "AdminLog",
    "CalendarReminder",
]
