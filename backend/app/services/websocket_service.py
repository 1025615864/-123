"""WebSocket服务 - 实时消息推送"""
import json
import logging
from typing import Any
from fastapi import WebSocket
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 活跃连接: {user_id: [websocket, ...]}
        self.active_connections: dict[int, list[WebSocket]] = {}
        # 匿名连接: [websocket, ...]
        self.anonymous_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket, user_id: int | None = None) -> None:
        """建立WebSocket连接"""
        await websocket.accept()
        
        if user_id:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)
            logger.info(f"User {user_id} connected via WebSocket")
        else:
            self.anonymous_connections.append(websocket)
            logger.info("Anonymous user connected via WebSocket")
    
    def disconnect(self, websocket: WebSocket, user_id: int | None = None) -> None:
        """断开WebSocket连接"""
        if user_id and user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected from WebSocket")
        elif websocket in self.anonymous_connections:
            self.anonymous_connections.remove(websocket)
            logger.info("Anonymous user disconnected from WebSocket")
    
    async def send_personal_message(
        self, 
        user_id: int, 
        message: dict[str, Any]
    ) -> bool:
        """发送个人消息"""
        if user_id not in self.active_connections:
            return False
        
        message_json = json.dumps(message, ensure_ascii=False, default=str)
        sent = False
        
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_text(message_json)
                sent = True
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
        
        return sent
    
    async def broadcast(self, message: dict[str, Any]) -> int:
        """广播消息给所有用户"""
        message_json = json.dumps(message, ensure_ascii=False, default=str)
        sent_count = 0
        
        # 发送给已登录用户
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_text(message_json)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Broadcast failed for user {user_id}: {e}")
        
        # 发送给匿名用户
        for connection in self.anonymous_connections:
            try:
                await connection.send_text(message_json)
                sent_count += 1
            except Exception:
                pass
        
        return sent_count
    
    def get_online_users(self) -> list[int]:
        """获取在线用户列表"""
        return list(self.active_connections.keys())
    
    def get_user_connection_count(self, user_id: int) -> int:
        """获取用户连接数"""
        return len(self.active_connections.get(user_id, []))
    
    def get_total_connections(self) -> int:
        """获取总连接数"""
        user_count = sum(len(conns) for conns in self.active_connections.values())
        return user_count + len(self.anonymous_connections)


# 全局连接管理器实例
manager = ConnectionManager()


# 消息类型定义
class MessageType:
    """消息类型常量"""
    NOTIFICATION = "notification"      # 通知消息
    CHAT_MESSAGE = "chat_message"      # 聊天消息
    SYSTEM = "system"                  # 系统消息
    COMMENT = "comment"                # 评论消息
    REPLY = "reply"                    # 回复消息
    LIKE = "like"                      # 点赞消息
    BOOKING = "booking"                # 预约消息


def create_message(
    msg_type: str,
    title: str,
    content: str,
    data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """创建标准消息格式"""
    return {
        "type": msg_type,
        "title": title,
        "content": content,
        "data": data or {},
        "timestamp": datetime.now().isoformat()
    }


async def notify_user(
    user_id: int,
    msg_type: str,
    title: str,
    content: str,
    data: dict[str, Any] | None = None
) -> bool:
    """发送通知给指定用户"""
    message = create_message(msg_type, title, content, data)
    return await manager.send_personal_message(user_id, message)


async def broadcast_system_message(title: str, content: str) -> int:
    """广播系统消息"""
    message = create_message(MessageType.SYSTEM, title, content)
    return await manager.broadcast(message)
