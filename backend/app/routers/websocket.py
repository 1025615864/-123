"""WebSocket路由"""
import logging
from typing import Annotated
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from ..config import get_settings
from ..database import AsyncSessionLocal
from ..models.user import User
from ..services.websocket_service import manager, MessageType, create_message
from ..utils.security import decode_token

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


def _get_token_from_websocket(websocket: WebSocket, query_token: str | None) -> str | None:
    auth = websocket.headers.get("authorization")
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
    return query_token


async def _get_active_user_id(token: str | None) -> int | None:
    if not token:
        return None

    payload = decode_token(token)
    if payload is None:
        return None

    sub = payload.get("sub")
    try:
        user_id = int(str(sub))
    except (TypeError, ValueError):
        return None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        if not user.is_active:
            return None
        return user.id


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
):
    """
    WebSocket连接端点
    
    连接方式: ws://host/ws?token=<jwt_token>
    
    消息格式:
    {
        "type": "notification|chat_message|system",
        "title": "消息标题",
        "content": "消息内容",
        "data": {},
        "timestamp": "2024-01-01T00:00:00"
    }
    """
    auth_token = _get_token_from_websocket(websocket, token)
    user_id = await _get_active_user_id(auth_token)

    if auth_token and user_id is None:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user_id)
    
    try:
        # 发送连接成功消息
        welcome_msg = create_message(
            MessageType.SYSTEM,
            "连接成功",
            "WebSocket连接已建立",
            {"user_id": user_id, "online_count": manager.get_total_connections()}
        )
        await websocket.send_json(welcome_msg)
        
        # 保持连接并处理消息
        while True:
            data = await websocket.receive_text()
            
            # 心跳检测
            if data == "ping":
                await websocket.send_text("pong")
                continue
            
            # 可以在这里处理客户端发送的其他消息
            logger.debug(f"Received from user {user_id}: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"User {user_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)


@router.get("/ws/status")
async def websocket_status():
    """获取WebSocket连接状态"""
    return {
        "total_connections": manager.get_total_connections(),
        "online_users": manager.get_online_users(),
        "anonymous_count": len(manager.anonymous_connections)
    }
