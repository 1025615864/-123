"""数据模型"""
from .user import User
from .user_quota import UserQuotaDaily, UserQuotaPackBalance
from .user_consent import UserConsent
from .consultation import Consultation, ChatMessage
from .consultation_review import ConsultationReviewTask, ConsultationReviewVersion
from .forum import Post, Comment, PostLike, CommentLike, PostFavorite, PostReaction
from .news import News, NewsFavorite, NewsViewHistory, NewsSubscription
from .news_ai import NewsAIAnnotation
from .news_workbench import NewsVersion, NewsAIGeneration, NewsLinkCheck
from .lawfirm import LawFirm, Lawyer, LawyerConsultation, LawyerConsultationMessage, LawyerReview
from .knowledge import LegalKnowledge, ConsultationTemplate
from .document import GeneratedDocument
from .document_template import DocumentTemplate, DocumentTemplateVersion
from .notification import Notification
from .system import SystemConfig, AdminLog
from .calendar import CalendarReminder
from .feedback import FeedbackTicket
from .settlement import LawyerWallet, LawyerIncomeRecord, LawyerBankAccount, WithdrawalRequest
from .payment import PaymentOrder, UserBalance, BalanceTransaction, PaymentCallbackEvent

__all__ = [
    "User", 
    "UserQuotaDaily",
    "UserQuotaPackBalance",
    "UserConsent",
    "Consultation", 
    "ChatMessage",
    "ConsultationReviewTask",
    "ConsultationReviewVersion",
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
    "GeneratedDocument",
    "DocumentTemplate",
    "DocumentTemplateVersion",
    "PostReaction",
    "Notification",
    "SystemConfig",
    "AdminLog",
    "CalendarReminder",
    "FeedbackTicket",
    "LawyerWallet",
    "LawyerIncomeRecord",
    "LawyerBankAccount",
    "WithdrawalRequest",
    "PaymentOrder",
    "UserBalance",
    "BalanceTransaction",
    "PaymentCallbackEvent",
]
