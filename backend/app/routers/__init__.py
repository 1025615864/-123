"""API路由"""

from fastapi import APIRouter

from . import admin, document, forum, knowledge, lawfirm, news, notification, payment, search, system, upload, user

try:
    from . import ai
except Exception:
    ai = None

api_router = APIRouter()

if ai is not None:
    api_router.include_router(ai.router)
api_router.include_router(user.router)
api_router.include_router(forum.router)
api_router.include_router(news.router)
api_router.include_router(lawfirm.router)
api_router.include_router(admin.router)
api_router.include_router(upload.router)
api_router.include_router(knowledge.router)
api_router.include_router(notification.router)
api_router.include_router(system.router)
api_router.include_router(document.router)
api_router.include_router(search.router)
api_router.include_router(payment.router)
