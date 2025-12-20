/**
 * WebSocket Hook - 实时消息接收
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "../contexts/AuthContext";

export interface WebSocketMessage {
  type:
    | "notification"
    | "chat_message"
    | "system"
    | "comment"
    | "reply"
    | "like"
    | "booking";
  title: string;
  content: string;
  data: Record<string, unknown>;
  timestamp: string;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  sendMessage: (data: string) => void;
  connect: () => void;
  disconnect: () => void;
}

export function useWebSocket(
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const { token } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  const getWebSocketUrl = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const envApiBaseUrl = (import.meta.env.VITE_API_BASE_URL ??
      import.meta.env.VITE_API_URL ??
      "") as string;

    if (envApiBaseUrl) {
      let host = envApiBaseUrl.replace(/^https?:\/\//, "").replace(/\/+$/, "");
      host = host.replace(/\/?api\/?$/, "");
      const url = `${protocol}//${host}/ws`;
      return token ? `${url}?token=${token}` : url;
    }

    const url = `${protocol}//${window.location.host}/ws`;
    return token ? `${url}?token=${token}` : url;
  }, [token]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const url = getWebSocketUrl();
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;
        onConnect?.();
      };

      wsRef.current.onmessage = (event) => {
        try {
          // 处理心跳响应
          if (event.data === "pong") {
            return;
          }

          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          onMessage?.(message);
        } catch (error) {
          console.error("Failed to parse WebSocket message:", error);
        }
      };

      wsRef.current.onclose = () => {
        console.log("WebSocket disconnected");
        setIsConnected(false);
        onDisconnect?.();

        // 自动重连
        if (
          autoReconnect &&
          reconnectAttemptsRef.current < maxReconnectAttempts
        ) {
          reconnectAttemptsRef.current += 1;
          console.log(
            `Reconnecting... attempt ${reconnectAttemptsRef.current}`
          );
          reconnectTimerRef.current = window.setTimeout(
            connect,
            reconnectInterval
          );
        }
      };

      wsRef.current.onerror = (error) => {
        console.error("WebSocket error:", error);
        onError?.(error);
      };
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
    }
  }, [
    getWebSocketUrl,
    onConnect,
    onDisconnect,
    onError,
    onMessage,
    autoReconnect,
    reconnectInterval,
    maxReconnectAttempts,
  ]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    reconnectAttemptsRef.current = maxReconnectAttempts; // 阻止自动重连
    wsRef.current?.close();
  }, [maxReconnectAttempts]);

  const sendMessage = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    } else {
      console.warn("WebSocket is not connected");
    }
  }, []);

  // 心跳保活
  useEffect(() => {
    if (!isConnected) return;

    const pingInterval = setInterval(() => {
      sendMessage("ping");
    }, 30000);

    return () => clearInterval(pingInterval);
  }, [isConnected, sendMessage]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, []);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    connect,
    disconnect,
  };
}

export default useWebSocket;
