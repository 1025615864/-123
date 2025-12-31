import {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import { useSearchParams, Link, useLocation } from "react-router-dom";
import {
  Send,
  Bot,
  User,
  History,
  Plus,
  BookOpen,
  Brain,
  Search,
  FileText,
  Lightbulb,
  Info,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Square,
  Mic,
  MicOff,
  Paperclip,
} from "lucide-react";
import api from "../api/client";
import { useAppMutation, useToast } from "../hooks";
import { getApiErrorMessage } from "../utils";
import PageHeader from "../components/PageHeader";
import { Button, Modal } from "../components/ui";
import MessageActionsBar from "../components/chat/MessageActionsBar";
import TemplateSelector from "../components/TemplateSelector";
import { useTheme } from "../contexts/ThemeContext";
import { useAuth } from "../contexts/AuthContext";

interface LawReference {
  law_name: string;
  article: string;
  content: string;
  relevance: number;
}

interface ThinkingStep {
  type: "intent" | "retrieval" | "analysis" | "generation";
  title: string;
  content: string;
  duration?: number;
  metadata?: Record<string, any>;
}

interface SearchQualityInfo {
  total_candidates: number;
  qualified_count: number;
  avg_similarity: number;
  confidence: string;
}

interface Message {
  id?: number;
  role: "user" | "assistant";
  content: string;
  references?: LawReference[];
  quickReplies?: string[];
  thinkingSteps?: ThinkingStep[];
  isThinking?: boolean;
  intent?: string;
  needsClarification?: boolean;
  clarifyingQuestions?: string[];
  strategyUsed?: string;
  strategyReason?: string;
  confidence?: string;
  riskLevel?: string;
  searchQuality?: SearchQualityInfo;
  disclaimer?: string;
}

const GUEST_AI_LIMIT = 5;
const GUEST_AI_USED_KEY = "guest_ai_used";
const GUEST_AI_RESET_AT_KEY = "guest_ai_reset_at";
const GUEST_AI_WINDOW_MS = 24 * 60 * 60 * 1000;

export default function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const sessionId = searchParams.get("session");
  const draft = searchParams.get("draft");
  const { actualTheme } = useTheme();
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  const [guestResetAt, setGuestResetAt] = useState<number | null>(() => {
    const raw = localStorage.getItem(GUEST_AI_RESET_AT_KEY);
    const n = raw == null ? NaN : Number(raw);
    if (!Number.isFinite(n) || n <= 0) return null;
    if (Date.now() > n) {
      localStorage.removeItem(GUEST_AI_USED_KEY);
      localStorage.removeItem(GUEST_AI_RESET_AT_KEY);
      return null;
    }
    return n;
  });
  const [guestUsed, setGuestUsed] = useState<number>(() => {
    const raw = localStorage.getItem(GUEST_AI_USED_KEY);
    const n = raw == null ? 0 : Number(raw);
    if (!Number.isFinite(n) || n <= 0) return 0;
    return Math.min(GUEST_AI_LIMIT, Math.floor(n));
  });
  const guestRemaining = Math.max(0, GUEST_AI_LIMIT - guestUsed);

  const [messages, setMessages] = useState<Message[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(
    sessionId
  );
  const [input, setInput] = useState("");
  const [showTemplateSelector, setShowTemplateSelector] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [analyzingFile, setAnalyzingFile] = useState(false);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const streamingAssistantIndexRef = useRef<number | null>(null);
  const streamingAbortRef = useRef<AbortController | null>(null);
  const skipNextLoadSessionIdRef = useRef<string | null>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const recordingChunksRef = useRef<BlobPart[]>([]);
  const toast = useToast();

  const handleChatScroll = useCallback(() => {
    const el = chatScrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const near = distanceFromBottom <= 120;
    setIsNearBottom(near);
    setShowScrollToBottom(!near);
  }, []);

  const resizeInput = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    const next = Math.min(el.scrollHeight, 200);
    el.style.height = `${next}px`;
  }, []);

  const stopRecordingTracks = useCallback(() => {
    const stream = recordingStreamRef.current;
    if (!stream) return;
    try {
      stream.getTracks().forEach((t) => {
        try {
          t.stop();
        } catch {}
      });
    } catch {}
    recordingStreamRef.current = null;
  }, []);

  const scrollToBottom = useCallback(
    (behavior: ScrollBehavior = "smooth") => {
      messagesEndRef.current?.scrollIntoView({ behavior });
    },
    []
  );

  const toggleRecording = useCallback(async () => {
    if (recording) {
      try {
        recorderRef.current?.stop();
      } catch {}
      setRecording(false);
      return;
    }

    if (loading || streaming || transcribing) return;

    if (!(navigator as any)?.mediaDevices?.getUserMedia) {
      toast.error("当前浏览器不支持语音输入");
      return;
    }
    if (!(window as any)?.MediaRecorder) {
      toast.error("当前浏览器不支持语音输入");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordingStreamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recordingChunksRef.current = [];

      recorder.ondataavailable = (evt: any) => {
        try {
          const data = evt?.data;
          if (data && typeof data.size === "number" && data.size > 0) {
            recordingChunksRef.current.push(data);
          }
        } catch {}
      };

      recorder.onstop = () => {
        const mimeType = String((recorder as any)?.mimeType || "audio/webm");
        const chunks = recordingChunksRef.current;
        recordingChunksRef.current = [];
        recorderRef.current = null;
        stopRecordingTracks();

        const blob = new Blob(chunks, { type: mimeType || "audio/webm" });
        if (!blob || blob.size <= 0) {
          toast.error("录音失败，请重试");
          return;
        }

        void (async () => {
          try {
            setTranscribing(true);
            const fd = new FormData();
            const ext = mimeType.includes("wav")
              ? "wav"
              : mimeType.includes("ogg")
              ? "ogg"
              : "webm";
            fd.append("file", blob, `recording.${ext}`);
            const res = await api.post("/ai/transcribe", fd, {
              headers: { "Content-Type": "multipart/form-data" },
            });
            const text = String(res?.data?.text ?? "").trim();
            if (!text) {
              toast.error("语音转写失败，请重试");
              return;
            }
            setInput((prev) => {
              const base = String(prev ?? "").trim();
              return base ? `${base}\n${text}` : text;
            });
            requestAnimationFrame(() => inputRef.current?.focus());
          } catch (e) {
            toast.error(getApiErrorMessage(e, "语音转写失败，请稍后再试"));
          } finally {
            setTranscribing(false);
          }
        })();
      };

      recorder.start();
      setRecording(true);
    } catch (e) {
      stopRecordingTracks();
      recorderRef.current = null;
      setRecording(false);
      toast.error(getApiErrorMessage(e, "无法开始录音"));
    }
  }, [loading, recording, stopRecordingTracks, streaming, toast, transcribing]);

  useEffect(() => {
    return () => {
      try {
        recorderRef.current?.stop();
      } catch {}
      recorderRef.current = null;
      stopRecordingTracks();
    };
  }, [stopRecordingTracks]);

  const handleAnalyzeFile = useCallback(
    async (file: File) => {
      if (!file) return;
      if (loading || streaming || transcribing || analyzingFile) return;

      try {
        setAnalyzingFile(true);
        const fd = new FormData();
        fd.append("file", file, file.name);
        const res = await api.post("/ai/files/analyze", fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const filename = String(res?.data?.filename ?? file.name).trim() || file.name;
        const summary = String(res?.data?.summary ?? "").trim();
        if (!summary) {
          toast.error("文件分析失败，请重试");
          return;
        }

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `【文件分析：${filename}】\n${summary}`,
          },
        ]);
        requestAnimationFrame(() => scrollToBottom());
      } catch (e) {
        toast.error(getApiErrorMessage(e, "文件分析失败，请稍后再试"));
      } finally {
        setAnalyzingFile(false);
      }
    },
    [analyzingFile, loading, scrollToBottom, streaming, toast, transcribing]
  );

  const loadSession = useCallback(async (sid: string) => {
    try {
      setLoading(true);
      const res = await api.get(`/ai/consultations/${sid}`);
      const data = res.data;
      if (data && data.messages) {
        setMessages(
          data.messages.map(
            (m: {
              id?: number;
              role: string;
              content: string;
              references?: string | null;
            }) => {
              let refs: LawReference[] | undefined = undefined;
              if (m.references) {
                try {
                  const parsed = JSON.parse(m.references);
                  if (Array.isArray(parsed)) {
                    refs = parsed as LawReference[];
                  }
                } catch {
                  refs = undefined;
                }
              }

              return {
                id: m.id,
                role: m.role as "user" | "assistant",
                content: m.content,
                references: refs,
              };
            }
          )
        );
        setCurrentSessionId(sid);
      }
    } catch {
      resetChat();
    } finally {
      setLoading(false);
    }
  }, []);

  const resetChat = () => {
    setMessages([
      {
        role: "assistant",
        content:
          "您好！我是百姓法律助手，一个专业的AI法律顾问。我可以为您解答各类法律问题，包括但不限于：劳动法、婚姻家庭、合同纠纷、消费者权益等。请问有什么可以帮助您的？",
      },
    ]);
    setCurrentSessionId(null);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("session");
      return next;
    });
  };

  useEffect(() => {
    if (sessionId) {
      if (skipNextLoadSessionIdRef.current === sessionId) {
        skipNextLoadSessionIdRef.current = null;
        return;
      }
      loadSession(sessionId);
    } else {
      resetChat();
    }
  }, [sessionId, loadSession]);

  useEffect(() => {
    if (sessionId) return;
    const raw = String(draft ?? "").trim();
    if (!raw) return;
    setInput(raw);
    window.setTimeout(() => inputRef.current?.focus(), 0);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("draft");
      return next;
    });
  }, [draft, sessionId, setSearchParams]);

  useEffect(() => {
    if (!isAuthenticated) return;
    if (!currentSessionId) return;
    skipNextLoadSessionIdRef.current = currentSessionId;
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("session", currentSessionId);
      return next;
    });
  }, [currentSessionId, isAuthenticated, setSearchParams]);

  const quickPrompts = useMemo(
    () => [
      "劳动合同试用期最长多久？",
      "离婚时房产如何分割？",
      "被拖欠工资如何维权？",
      "租房押金不退怎么办？",
    ],
    []
  );

  useEffect(() => {
    if (streaming) {
      if (!isNearBottom) return;
      scrollToBottom("auto");
      return;
    }

    if (isNearBottom) {
      scrollToBottom("smooth");
    }
  }, [messages, scrollToBottom, streaming, isNearBottom]);

  useEffect(() => {
    requestAnimationFrame(() => {
      handleChatScroll();
    });
  }, [handleChatScroll, messages.length]);

  useEffect(() => {
    resizeInput();
  }, [input, resizeInput]);

  const sendMessage = async (overrideMessage?: string) => {
    const picked = String(overrideMessage ?? input).trim();
    if (!picked || loading || streaming) return;

    const userMessage = picked;

    const token = localStorage.getItem("token");
    const isGuest = !token;
    let localGuestUsed = guestUsed;
    let localGuestResetAt = guestResetAt;

    if (
      isGuest &&
      localGuestResetAt != null &&
      Date.now() > localGuestResetAt
    ) {
      localGuestUsed = 0;
      localGuestResetAt = null;
      setGuestUsed(0);
      setGuestResetAt(null);
      localStorage.removeItem(GUEST_AI_USED_KEY);
      localStorage.removeItem(GUEST_AI_RESET_AT_KEY);
    }

    if (isGuest && Math.max(0, GUEST_AI_LIMIT - localGuestUsed) <= 0) {
      toast.info("游客模式 24 小时内仅可试用 5 次，请登录后继续");
      return;
    }

    let guestCounted = false;
    const countGuestIfNeeded = () => {
      if (!isGuest || guestCounted) return;
      guestCounted = true;

      const now = Date.now();
      if (localGuestResetAt == null || now > localGuestResetAt) {
        localGuestUsed = 0;
        localGuestResetAt = now + GUEST_AI_WINDOW_MS;
        setGuestUsed(0);
        setGuestResetAt(localGuestResetAt);
        localStorage.setItem(GUEST_AI_USED_KEY, "0");
        localStorage.setItem(GUEST_AI_RESET_AT_KEY, String(localGuestResetAt));
      } else {
        setGuestResetAt(localGuestResetAt);
      }

      const nextUsed = Math.min(GUEST_AI_LIMIT, localGuestUsed + 1);
      localGuestUsed = nextUsed;
      setGuestUsed(nextUsed);
      localStorage.setItem(GUEST_AI_USED_KEY, String(nextUsed));
    };

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    requestAnimationFrame(() => {
      scrollToBottom("smooth");
    });

    let pendingRaf: number | null = null;
    let flushPendingText: (() => void) | null = null;
    let assistantText = "";

    const applyQuickReplies = (replies: unknown) => {
      if (!Array.isArray(replies)) return;
      const cleaned = replies
        .filter((r) => typeof r === "string" && r.trim())
        .map((r) => String(r).trim())
        .slice(0, 6);
      if (cleaned.length === 0) return;
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i]?.role === "assistant") {
            next[i] = { ...next[i], quickReplies: cleaned };
            break;
          }
        }
        return next;
      });
    };

    const requestQuickReplies = async (
      answer: string,
      refs: LawReference[]
    ) => {
      try {
        const res = await api.post("/ai/quick-replies", {
          user_message: userMessage,
          assistant_answer: answer,
          references: refs ?? [],
        });
        applyQuickReplies(res?.data?.replies);
      } catch {
        // ignore
      }
    };

    const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(
      /\/+$/,
      ""
    );
    const streamUrl = `${apiBaseUrl}/ai/chat/stream`;

    try {
      setStreaming(true);

      const abortController = new AbortController();
      streamingAbortRef.current = abortController;

      streamingAssistantIndexRef.current = null;
      setMessages((prev) => {
        streamingAssistantIndexRef.current = prev.length;
        return [
          ...prev,
          {
            role: "assistant",
            content: "",
            references: [],
            thinkingSteps: [],
            isThinking: true,
            intent: undefined,
            needsClarification: undefined,
            clarifyingQuestions: undefined,
            strategyUsed: undefined,
            strategyReason: undefined,
            confidence: undefined,
            riskLevel: undefined,
            searchQuality: undefined,
            disclaimer: undefined,
          },
        ];
      });

      const res = await fetch(streamUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: abortController.signal,
        body: JSON.stringify({
          message: userMessage,
          session_id: currentSessionId,
        }),
      });

      if (!res.ok) {
        const headerRequestId =
          res.headers.get("X-Request-Id") || res.headers.get("x-request-id");
        const headerErrorCode =
          res.headers.get("X-Error-Code") || res.headers.get("x-error-code");
        let message = "";
        let bodyRequestId: string | undefined;
        let bodyErrorCode: string | undefined;
        try {
          const raw = await res.text();
          message = raw;
          try {
            const parsed = JSON.parse(raw);
            message = parsed?.detail || parsed?.message || raw;
            bodyRequestId = parsed?.request_id;
            bodyErrorCode = parsed?.error_code;
          } catch {
            // ignore
          }
        } catch {
          message = "";
        }

        const err: any = new Error(message || `HTTP ${res.status}`);
        err.status = res.status;
        err.rateLimitReset = res.headers.get("X-RateLimit-Reset");
        err.retryAfter = res.headers.get("Retry-After");
        err.requestId = bodyRequestId || headerRequestId;
        err.errorCode = bodyErrorCode || headerErrorCode;
        throw err;
      }

      countGuestIfNeeded();

      if (!res.body) {
        throw new Error("浏览器不支持流式响应");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let pendingRefs: LawReference[] = [];
      let receivedSessionId: string | null = null;
      let pendingText = "";

      const applyAssistantUpdate = (updater: (m: Message) => Message) => {
        setMessages((prev) => {
          const next = [...prev];
          const idx = streamingAssistantIndexRef.current ?? next.length - 1;
          if (idx < 0 || idx >= next.length) return prev;
          const current = next[idx];
          if (!current || current.role !== "assistant") return prev;
          next[idx] = updater(current);
          return next;
        });
      };

      const flushTextNow = () => {
        if (pendingRaf != null) {
          cancelAnimationFrame(pendingRaf);
          pendingRaf = null;
        }
        if (!pendingText) return;
        const toAdd = pendingText;
        pendingText = "";
        applyAssistantUpdate((m) => ({
          ...m,
          content: (m.content ?? "") + toAdd,
        }));
      };

      flushPendingText = flushTextNow;

      const scheduleAppendText = (text: string) => {
        pendingText += text;
        if (pendingRaf != null) return;
        pendingRaf = requestAnimationFrame(() => {
          pendingRaf = null;
          flushTextNow();
        });
      };

      const handleEvent = (eventType: string, data: any) => {
        if (eventType === "session") {
          const sid = data?.session_id;
          if (typeof sid === "string" && sid.trim()) {
            receivedSessionId = sid;
            setCurrentSessionId(sid);
          }
          return;
        }
        if (eventType === "meta") {
          const intent = data?.intent;
          const needs = data?.needs_clarification;
          const questions = data?.clarifying_questions;

          const strategyUsed = data?.strategy_used;
          const strategyReason = data?.strategy_reason;
          const confidence = data?.confidence;
          const riskLevel = data?.risk_level;
          const searchQuality = data?.search_quality;
          const disclaimer = data?.disclaimer;

          const cleanedQuestions = Array.isArray(questions)
            ? questions
                .filter((q) => typeof q === "string" && q.trim())
                .map((q) => String(q).trim())
                .slice(0, 6)
            : undefined;

          const cleanedSearchQuality =
            searchQuality && typeof searchQuality === "object"
              ? {
                  total_candidates: Number(searchQuality.total_candidates ?? 0),
                  qualified_count: Number(searchQuality.qualified_count ?? 0),
                  avg_similarity: Number(searchQuality.avg_similarity ?? 0),
                  confidence: String(searchQuality.confidence ?? ""),
                }
              : undefined;

          applyAssistantUpdate((m) => ({
            ...m,
            intent: typeof intent === "string" ? intent : m.intent,
            needsClarification:
              typeof needs === "boolean" ? needs : m.needsClarification,
            clarifyingQuestions: cleanedQuestions ?? m.clarifyingQuestions,
            strategyUsed:
              typeof strategyUsed === "string" ? strategyUsed : m.strategyUsed,
            strategyReason:
              typeof strategyReason === "string"
                ? strategyReason
                : m.strategyReason,
            confidence:
              typeof confidence === "string" ? confidence : m.confidence,
            riskLevel:
              typeof riskLevel === "string" ? riskLevel : m.riskLevel,
            searchQuality: cleanedSearchQuality ?? m.searchQuality,
            disclaimer:
              typeof disclaimer === "string" ? disclaimer : m.disclaimer,
          }));
          return;
        }
        if (eventType === "thinking") {
          const steps = data?.steps;
          const isThinking = data?.is_thinking;
          if (Array.isArray(steps)) {
            applyAssistantUpdate((m) => ({
              ...m,
              thinkingSteps: steps as ThinkingStep[],
              isThinking: typeof isThinking === "boolean" ? isThinking : true,
            }));
          } else if (typeof isThinking === "boolean") {
            applyAssistantUpdate((m) => ({
              ...m,
              isThinking,
            }));
          }
          return;
        }
        if (eventType === "references") {
          const refs = data?.references;
          if (Array.isArray(refs)) {
            pendingRefs = refs as LawReference[];
            applyAssistantUpdate((m) => ({ ...m, references: pendingRefs }));
          }
          return;
        }
        if (eventType === "content") {
          const text = data?.text;
          if (typeof text === "string" && text.length > 0) {
            assistantText += text;
            scheduleAppendText(text);
          }
          return;
        }
        if (eventType === "done") {
          flushTextNow();
          if (receivedSessionId) {
            setCurrentSessionId(receivedSessionId);
          }

          const mid = data?.assistant_message_id;
          if (typeof mid === "number") {
            applyAssistantUpdate((m) => ({ ...m, id: mid }));
          }

          applyAssistantUpdate((m) => ({ ...m, isThinking: false }));

          const persistError = data?.persist_error;
          if (typeof persistError === "string" && persistError.trim()) {
            const requestId = data?.request_id;
            const doneErrorCode = data?.error_code;
            const requestIdSuffix =
              typeof requestId === "string" && requestId.trim()
                ? `（请求ID: ${requestId}）`
                : "";
            const errorCodeSuffix =
              typeof doneErrorCode === "string" && doneErrorCode.trim()
                ? `（错误码: ${doneErrorCode}）`
                : "";
            const suffix = `${errorCodeSuffix}${requestIdSuffix}`;
            if (persistError === "persist_failed") {
              toast.warning(
                `本次回答已生成，但保存失败，历史记录可能不会显示（可稍后重试或刷新）。${suffix}`
              );
            } else if (persistError === "persist_forbidden") {
              toast.warning(
                `本次回答已生成，但无权限保存到该会话，历史记录可能不会显示。${suffix}`
              );
            } else if (persistError === "stream_failed") {
              toast.warning(
                `本次回答可能未完整生成或未能保存（可稍后重试）。${suffix}`
              );
            } else {
              toast.warning(
                `本次回答已生成，但保存状态异常，历史记录可能不会显示。${suffix}`
              );
            }
          }

          void requestQuickReplies(assistantText, pendingRefs);
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const chunks = buffer.split(/\r?\n\r?\n/);
        buffer = chunks.pop() ?? "";

        for (const chunk of chunks) {
          const lines = chunk.split(/\r?\n/).filter((l) => l.trim().length > 0);
          let eventType = "message";
          let dataLine = "";
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataLine += line.slice(5).trim();
            }
          }

          if (!dataLine) continue;
          try {
            const data = JSON.parse(dataLine);
            handleEvent(eventType, data);
          } catch {
            // ignore parse errors
          }
        }
      }

      return;
    } catch (err: any) {
      if (err?.name === "AbortError") {
        toast.info("已停止生成");
        return;
      }

      const status = err?.status;
      const message = err?.message || "请求失败，请稍后再试。";

      if (status === 401) {
        try {
          localStorage.removeItem("token");
          window.dispatchEvent(new Event("auth:logout"));
        } catch {
          // ignore
        }

        toast.info("登录已过期，请重新登录");
        setMessages((prev) => {
          const idx = streamingAssistantIndexRef.current;
          const content = "登录已过期，请重新登录后继续使用。";
          if (idx == null || idx < 0 || idx >= prev.length) {
            return [...prev, { role: "assistant", content }];
          }
          const next = [...prev];
          const current = next[idx];
          if (!current || current.role !== "assistant") return prev;
          next[idx] = { ...current, content };
          return next;
        });
        return;
      }

      if (status === 429) {
        if (isGuest) {
          setGuestUsed(GUEST_AI_LIMIT);
          localStorage.setItem(GUEST_AI_USED_KEY, String(GUEST_AI_LIMIT));

          const resetRaw = err?.rateLimitReset;
          const resetSeconds = resetRaw == null ? NaN : Number(resetRaw);
          if (Number.isFinite(resetSeconds) && resetSeconds > 0) {
            const resetAtMs = resetSeconds * 1000;
            setGuestResetAt(resetAtMs);
            localStorage.setItem(GUEST_AI_RESET_AT_KEY, String(resetAtMs));
          }
        }
        setMessages((prev) => {
          const idx = streamingAssistantIndexRef.current;
          if (idx == null || idx < 0 || idx >= prev.length) {
            return [...prev, { role: "assistant", content: message }];
          }
          const next = [...prev];
          const current = next[idx];
          if (!current || current.role !== "assistant") return prev;
          next[idx] = { ...current, content: message };
          return next;
        });
        return;
      }

      setMessages((prev) => {
        const idx = streamingAssistantIndexRef.current;
        if (idx == null || idx < 0 || idx >= prev.length) {
          return [
            ...prev,
            {
              role: "assistant",
              content: `抱歉，本次请求失败：${message}`,
            },
          ];
        }
        const next = [...prev];
        const current = next[idx];
        if (!current || current.role !== "assistant") return prev;
        next[idx] = {
          ...current,
          content: `抱歉，本次请求失败：${message}`,
        };
        return next;
      });

      // fallback to non-stream API when stream fails
      try {
        setLoading(true);
        const res = await api.post("/ai/chat", {
          message: userMessage,
          session_id: currentSessionId,
        });
        const response = res.data;

        countGuestIfNeeded();

        setMessages((prev) => {
          const idx = streamingAssistantIndexRef.current;
          if (idx == null || idx < 0 || idx >= prev.length) {
            return [
              ...prev,
              {
                role: "assistant",
                content: response.answer,
                references: response.references || [],
                quickReplies: [],
                intent:
                  typeof response.intent === "string" ? response.intent : undefined,
                needsClarification:
                  typeof response.needs_clarification === "boolean"
                    ? response.needs_clarification
                    : undefined,
                clarifyingQuestions: Array.isArray(response.clarifying_questions)
                  ? response.clarifying_questions
                      .filter((q: any) => typeof q === "string" && q.trim())
                      .map((q: any) => String(q).trim())
                      .slice(0, 6)
                  : undefined,
                strategyUsed:
                  typeof response.strategy_used === "string"
                    ? response.strategy_used
                    : undefined,
                strategyReason:
                  typeof response.strategy_reason === "string"
                    ? response.strategy_reason
                    : undefined,
                confidence:
                  typeof response.confidence === "string"
                    ? response.confidence
                    : undefined,
                riskLevel:
                  typeof response.risk_level === "string"
                    ? response.risk_level
                    : undefined,
                searchQuality:
                  response.search_quality && typeof response.search_quality === "object"
                    ? {
                        total_candidates: Number(
                          response.search_quality.total_candidates ?? 0
                        ),
                        qualified_count: Number(
                          response.search_quality.qualified_count ?? 0
                        ),
                        avg_similarity: Number(
                          response.search_quality.avg_similarity ?? 0
                        ),
                        confidence: String(response.search_quality.confidence ?? ""),
                      }
                    : undefined,
                disclaimer:
                  typeof response.disclaimer === "string"
                    ? response.disclaimer
                    : undefined,
              },
            ];
          }
          const next = [...prev];
          const current = next[idx];
          if (!current || current.role !== "assistant") return prev;
          next[idx] = {
            ...current,
            content: response.answer,
            references: response.references || [],
            quickReplies: current.quickReplies || [],
            intent:
              typeof response.intent === "string" ? response.intent : current.intent,
            needsClarification:
              typeof response.needs_clarification === "boolean"
                ? response.needs_clarification
                : current.needsClarification,
            clarifyingQuestions: Array.isArray(response.clarifying_questions)
              ? response.clarifying_questions
                  .filter((q: any) => typeof q === "string" && q.trim())
                  .map((q: any) => String(q).trim())
                  .slice(0, 6)
              : current.clarifyingQuestions,
            strategyUsed:
              typeof response.strategy_used === "string"
                ? response.strategy_used
                : current.strategyUsed,
            strategyReason:
              typeof response.strategy_reason === "string"
                ? response.strategy_reason
                : current.strategyReason,
            confidence:
              typeof response.confidence === "string"
                ? response.confidence
                : current.confidence,
            riskLevel:
              typeof response.risk_level === "string"
                ? response.risk_level
                : current.riskLevel,
            searchQuality:
              response.search_quality && typeof response.search_quality === "object"
                ? {
                    total_candidates: Number(
                      response.search_quality.total_candidates ?? 0
                    ),
                    qualified_count: Number(
                      response.search_quality.qualified_count ?? 0
                    ),
                    avg_similarity: Number(
                      response.search_quality.avg_similarity ?? 0
                    ),
                    confidence: String(response.search_quality.confidence ?? ""),
                  }
                : current.searchQuality,
            disclaimer:
              typeof response.disclaimer === "string"
                ? response.disclaimer
                : current.disclaimer,
            id:
              typeof response.assistant_message_id === "number"
                ? response.assistant_message_id
                : current.id,
          };
          return next;
        });

        if (response.session_id) {
          setCurrentSessionId(response.session_id);
        }

        void requestQuickReplies(
          String(response.answer ?? ""),
          Array.isArray(response.references)
            ? (response.references as LawReference[])
            : []
        );
      } catch (e) {
        toast.error(getApiErrorMessage(e, "请求失败，请稍后再试。"));
      } finally {
        setLoading(false);
      }
    } finally {
      try {
        flushPendingText?.();
      } catch {
        // ignore
      }
      setStreaming(false);
      streamingAssistantIndexRef.current = null;
      streamingAbortRef.current = null;
    }
  };

  const stopStreaming = () => {
    try {
      streamingAbortRef.current?.abort();
    } catch {
      // ignore
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (streaming) {
        stopStreaming();
        return;
      }
      void sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] h-[calc(100dvh-140px)] w-full max-w-5xl mx-auto">
      <div className="flex-none px-4 sm:px-0 mb-6">
        <PageHeader
          eyebrow="AI智能咨询"
          title="法律咨询助手"
          description="24小时在线，为您提供专业的法律解答。AI建议仅供参考。"
          layout="mdStart"
          tone={actualTheme}
          right={
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setShowTemplateSelector(true)}
                  className="px-3 sm:px-4 shadow-md"
                >
                  <Sparkles className="h-4 w-4 sm:mr-2" />
                  <span className="hidden sm:inline">快速咨询</span>
                </Button>
                <Link to="/chat/history">
                  <Button
                    variant="outline"
                    size="sm"
                    className="px-3 sm:px-4 bg-white/60 backdrop-blur-sm dark:bg-slate-800/50"
                  >
                    <History className="h-4 w-4 sm:mr-2" />
                    <span className="hidden sm:inline">历史记录</span>
                  </Button>
                </Link>
                {currentSessionId && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={resetChat}
                    className="px-3 sm:px-4 bg-white/60 backdrop-blur-sm dark:bg-slate-800/50"
                  >
                    <Plus className="h-4 w-4 sm:mr-2" />
                    <span className="hidden sm:inline">新对话</span>
                  </Button>
                )}
              </div>
            </div>
          }
        />
      </div>

      <div className="flex-1 flex flex-col min-h-0 bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-3xl border border-slate-200/70 dark:border-white/10 shadow-xl overflow-hidden relative">
        <div
          ref={chatScrollRef}
          onScroll={handleChatScroll}
          className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 scroll-smooth"
        >
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex gap-4 max-w-3xl mx-auto ${
                message.role === "user" ? "flex-row-reverse" : "flex-row"
              } animate-fade-in`}
            >
              <div className="flex-shrink-0">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center shadow-md ${
                    message.role === "assistant"
                      ? "bg-gradient-to-br from-blue-500 to-indigo-600 text-white"
                      : "bg-white text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  {message.role === "assistant" ? (
                    <Bot className="h-5 w-5" />
                  ) : (
                    <User className="h-5 w-5" />
                  )}
                </div>
              </div>

              <div
                className={`flex flex-col max-w-[85%] ${
                  message.role === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`px-5 py-4 rounded-2xl shadow-sm text-sm leading-relaxed transition-transform duration-200 ${
                    message.role === "user"
                      ? "bg-blue-600 text-white rounded-tr-sm"
                      : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-100 dark:border-slate-700 rounded-tl-sm"
                  }`}
                >
                  {message.role === "user" ? (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  ) : (
                    <AssistantMessage
                      messageId={message.id}
                      content={message.content}
                      references={message.references}
                      thinkingSteps={message.thinkingSteps}
                      isThinking={message.isThinking}
                      quickReplies={message.quickReplies}
                      intent={message.intent}
                      needsClarification={message.needsClarification}
                      clarifyingQuestions={message.clarifyingQuestions}
                      strategyUsed={message.strategyUsed}
                      strategyReason={message.strategyReason}
                      confidence={message.confidence}
                      riskLevel={message.riskLevel}
                      searchQuality={message.searchQuality}
                      disclaimer={message.disclaimer}
                      onRegenerate={() => {
                        let question = "";
                        for (let i = index - 1; i >= 0; i--) {
                          const m = messages[i];
                          if (m?.role === "user") {
                            question = String(m.content ?? "");
                            break;
                          }
                        }
                        if (!question.trim()) {
                          toast.info("未找到对应的上一条提问");
                          return;
                        }
                        void sendMessage(question);
                      }}
                      onQuickReplySelect={(text) => {
                        setInput(text);
                        requestAnimationFrame(() => inputRef.current?.focus());
                      }}
                      isStreaming={
                        streaming &&
                        index === streamingAssistantIndexRef.current
                      }
                    />
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} className="h-4" />
        </div>

        {showScrollToBottom && (
          <button
            type="button"
            onClick={() => {
              scrollToBottom("smooth");
              requestAnimationFrame(() => {
                handleChatScroll();
              });
            }}
            className="absolute bottom-28 right-6 z-10 rounded-full border border-slate-200/70 bg-white/90 p-3 text-slate-700 shadow-lg backdrop-blur-md transition-all hover:bg-white hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:border-white/10 dark:bg-slate-800/80 dark:text-slate-200 dark:hover:bg-slate-800 dark:focus-visible:ring-offset-slate-900"
            aria-label="回到底部"
          >
            <ChevronDown className="h-5 w-5" />
          </button>
        )}

        {/* Input Area */}
        <div className="p-4 sm:p-6 pb-[calc(1rem+env(safe-area-inset-bottom))] bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-t border-slate-200/50 dark:border-slate-700/50">
          <div className="max-w-3xl mx-auto space-y-4">
            {!isAuthenticated && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200/70 bg-slate-50 px-4 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300">
                <span>
                  游客模式：24小时内剩余{" "}
                  <span className="font-semibold text-slate-900 dark:text-white">
                    {guestRemaining}
                  </span>{" "}
                  / {GUEST_AI_LIMIT} 次
                  {guestResetAt && guestResetAt > Date.now() && (
                    <span className="text-slate-500 dark:text-slate-400">
                      {`（约 ${Math.max(
                        1,
                        Math.ceil((guestResetAt - Date.now()) / 3600000)
                      )} 小时后重置）`}
                    </span>
                  )}
                  。登录后可保存历史记录。
                </span>
                <Link
                  to={`/login?redirect=${encodeURIComponent(
                    `${location.pathname}${location.search}`
                  )}`}
                  className="font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                >
                  去登录
                </Link>
              </div>
            )}
            {messages.length < 2 && (
              <div className="flex flex-wrap gap-2 justify-center mb-2">
                {quickPrompts.map((p) => (
                  <button
                    key={p}
                    onClick={() => {
                      setInput(p);
                      requestAnimationFrame(() => inputRef.current?.focus());
                    }}
                    disabled={loading}
                    className="px-3 py-1.5 rounded-full bg-slate-100 hover:bg-slate-200 active:scale-[0.99] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/20 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:bg-slate-800 dark:hover:bg-slate-700 dark:focus-visible:ring-offset-slate-900 text-xs text-slate-600 dark:text-slate-300 transition-all"
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}

            <div className="relative shadow-lg rounded-3xl bg-white dark:bg-slate-800 ring-1 ring-slate-900/5 dark:ring-white/10 transition-shadow focus-within:ring-2 focus-within:ring-blue-500/50">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="输入您的法律问题..."
                rows={1}
                disabled={loading || streaming}
                className="w-full px-5 py-4 pr-40 rounded-3xl bg-transparent text-slate-900 dark:text-white placeholder:text-slate-400 outline-none resize-none max-h-48 text-sm leading-relaxed"
                style={{ minHeight: "56px" }}
              />
              <div className="absolute right-2 bottom-2 flex items-center gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  data-testid="chat-file-input"
                  accept=".pdf,.docx,.txt,.md,.csv,.json,application/pdf,text/plain,text/markdown,text/csv,application/json,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(e) => {
                    const picked = e.target.files?.[0];
                    e.target.value = "";
                    if (!picked) return;
                    void handleAnalyzeFile(picked);
                  }}
                />
                <Button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={loading || streaming || transcribing || analyzingFile}
                  isLoading={analyzingFile}
                  loadingText=""
                  size="sm"
                  aria-label="上传文件"
                  className="w-10 h-10 p-0 rounded-full transition-all bg-slate-100 hover:bg-slate-200 text-slate-600 shadow-md hover:shadow-lg dark:bg-slate-700 dark:hover:bg-slate-600 dark:text-slate-200"
                >
                  <Paperclip className="h-4 w-4" />
                </Button>
                <Button
                  onClick={toggleRecording}
                  disabled={loading || streaming || transcribing}
                  isLoading={transcribing}
                  loadingText=""
                  size="sm"
                  aria-label={recording ? "停止录音" : "语音输入"}
                  className={`w-10 h-10 p-0 rounded-full transition-all ${
                    recording
                      ? "bg-red-600 hover:bg-red-700 text-white shadow-md hover:shadow-lg"
                      : "bg-slate-100 hover:bg-slate-200 text-slate-600 shadow-md hover:shadow-lg dark:bg-slate-700 dark:hover:bg-slate-600 dark:text-slate-200"
                  }`}
                >
                  {recording ? (
                    <MicOff className="h-4 w-4" />
                  ) : (
                    <Mic className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  onClick={
                    streaming
                      ? stopStreaming
                      : () => {
                          void sendMessage();
                        }
                  }
                  disabled={loading || (!streaming && !input.trim())}
                  isLoading={loading}
                  loadingText=""
                  size="sm"
                  className={`w-10 h-10 p-0 rounded-full transition-all ${
                    input.trim() || streaming
                      ? "bg-blue-600 hover:bg-blue-700 text-white shadow-md hover:shadow-lg"
                      : "bg-slate-100 text-slate-400 dark:bg-slate-700"
                  }`}
                >
                  {streaming ? (
                    <Square className="h-4 w-4 fill-current" />
                  ) : (
                    <Send className="h-4 w-4 ml-0.5" />
                  )}
                </Button>
              </div>
            </div>
            <div className="text-center text-[10px] text-slate-400 dark:text-slate-500">
              AI 可能会犯错。请核查重要信息。
            </div>
          </div>
        </div>
      </div>

      {showTemplateSelector && (
        <TemplateSelector
          onSelectQuestion={(question) => {
            setInput(question);
            setShowTemplateSelector(false);
            requestAnimationFrame(() => inputRef.current?.focus());
          }}
          onClose={() => setShowTemplateSelector(false)}
          theme={actualTheme}
        />
      )}
    </div>
  );
}

function ThinkingProcess({
  steps,
  isThinking,
}: {
  steps?: ThinkingStep[];
  isThinking: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const normalizedSteps = Array.isArray(steps) ? steps : [];

  const stepIcon = (type: ThinkingStep["type"]) => {
    if (type === "intent") return Brain;
    if (type === "retrieval") return Search;
    if (type === "analysis") return FileText;
    return Lightbulb;
  };

  const stepColor = (type: ThinkingStep["type"]) => {
    if (type === "intent")
      return "text-purple-700 bg-purple-50 dark:text-purple-200 dark:bg-purple-900/30";
    if (type === "retrieval")
      return "text-blue-700 bg-blue-50 dark:text-blue-200 dark:bg-blue-900/30";
    if (type === "analysis")
      return "text-emerald-700 bg-emerald-50 dark:text-emerald-200 dark:bg-emerald-900/30";
    return "text-amber-700 bg-amber-50 dark:text-amber-200 dark:bg-amber-900/30";
  };

  if (normalizedSteps.length === 0 && !isThinking) return null;

  return (
    <div className="mb-3">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
      >
        <Brain className="w-4 h-4" />
        <span>AI 思考过程</span>
        {isThinking && (
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
            思考中...
          </span>
        )}
        {expanded ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
      </button>

      {expanded && (
        <div className="mt-2 space-y-2 pl-4 border-l-2 border-slate-200 dark:border-slate-700">
          {normalizedSteps.map((step, idx) => {
            const Icon = stepIcon(step.type);
            return (
              <div key={idx} className="flex items-start gap-2">
                <div className={`p-1 rounded ${stepColor(step.type)}`}>
                  <Icon className="w-3 h-3" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-medium text-slate-700 dark:text-slate-200">
                      {step.title}
                    </p>
                    {typeof step.duration === "number" && step.duration > 0 && (
                      <span className="text-[10px] text-slate-400 dark:text-slate-500">
                        {Math.round(step.duration)}ms
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 whitespace-pre-wrap">
                    {step.content}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AssistantMessage({
  messageId,
  content,
  references,
  thinkingSteps,
  isThinking,
  quickReplies,
  intent,
  needsClarification,
  clarifyingQuestions,
  strategyUsed,
  strategyReason,
  confidence,
  riskLevel,
  searchQuality,
  disclaimer,
  onRegenerate,
  onQuickReplySelect,
  isStreaming,
}: {
  messageId?: number;
  content: string;
  references?: LawReference[];
  thinkingSteps?: ThinkingStep[];
  isThinking?: boolean;
  quickReplies?: string[];
  intent?: string;
  needsClarification?: boolean;
  clarifyingQuestions?: string[];
  strategyUsed?: string;
  strategyReason?: string;
  confidence?: string;
  riskLevel?: string;
  searchQuality?: SearchQualityInfo;
  disclaimer?: string;
  onRegenerate?: () => void;
  onQuickReplySelect?: (text: string) => void;
  isStreaming?: boolean;
}) {
  const [showRefs, setShowRefs] = useState(false);
  const [activeRef, setActiveRef] = useState<LawReference | null>(null);
  const [favorited, setFavorited] = useState(false);
  const toast = useToast();
  const [rated, setRated] = useState<number | null>(null);
  const [showMeta, setShowMeta] = useState(false);

  const FAVORITES_KEY = "chat_favorite_messages_v1";

  useEffect(() => {
    if (!messageId) {
      setFavorited(false);
      return;
    }
    try {
      const raw = localStorage.getItem(FAVORITES_KEY);
      const parsed = raw ? JSON.parse(raw) : {};
      const isFav = Boolean(
        parsed && typeof parsed === "object" && parsed[String(messageId)]
      );
      setFavorited(isFav);
    } catch {
      setFavorited(false);
    }
  }, [messageId]);

  const toggleFavorite = () => {
    if (!messageId) return;
    try {
      const raw = localStorage.getItem(FAVORITES_KEY);
      const parsed = raw ? JSON.parse(raw) : {};
      const next: Record<string, any> =
        parsed && typeof parsed === "object" ? parsed : {};
      const key = String(messageId);
      if (next[key]) {
        delete next[key];
        localStorage.setItem(FAVORITES_KEY, JSON.stringify(next));
        setFavorited(false);
        toast.success("已取消收藏");
        return;
      }
      next[key] = {
        id: messageId,
        content,
        references: references ?? [],
        saved_at: new Date().toISOString(),
      };
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(next));
      setFavorited(true);
      toast.success("已收藏");
    } catch {
      toast.error("收藏失败");
    }
  };

  const rateMutation = useAppMutation<
    { message?: string },
    { message_id: number; rating: number }
  >({
    mutationFn: async (payload) => {
      const res = await api.post("/ai/messages/rate", payload);
      return res.data as { message?: string };
    },
    errorMessageFallback: "评价失败，请稍后重试",
    onSuccess: (res, payload) => {
      toast.success(res?.message ?? "评价成功");
      setRated(payload.rating);
    },
  });

  const blocks = useMemo(() => {
    const rawLines = content.replace(/\r\n/g, "\n").split("\n");
    const items: Array<{
      type: "h3" | "h2" | "quote" | "li" | "oli" | "p" | "br" | "code";
      text: string;
    }> = [];
    let inCode = false;
    let codeLines: string[] = [];

    for (const line of rawLines) {
      const t = line.trimEnd();
      const trimmed = t.trim();

      if (trimmed.startsWith("```")) {
        if (!inCode) {
          inCode = true;
          codeLines = [];
        } else {
          inCode = false;
          items.push({ type: "code", text: codeLines.join("\n") });
          codeLines = [];
        }
        continue;
      }

      if (inCode) {
        codeLines.push(line);
        continue;
      }

      if (!trimmed) {
        items.push({ type: "br", text: "" });
        continue;
      }

      if (trimmed.startsWith("### ")) {
        items.push({ type: "h3", text: trimmed.slice(4).trim() });
        continue;
      }
      if (trimmed.startsWith("## ")) {
        items.push({ type: "h2", text: trimmed.slice(3).trim() });
        continue;
      }
      if (trimmed.startsWith(">")) {
        items.push({ type: "quote", text: trimmed.replace(/^>\s?/, "") });
        continue;
      }
      if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
        items.push({ type: "li", text: trimmed.slice(2).trim() });
        continue;
      }
      if (/^\d+\.\s+/.test(trimmed)) {
        items.push({ type: "oli", text: trimmed.replace(/^\d+\.\s+/, "") });
        continue;
      }

      items.push({ type: "p", text: t });
    }

    if (inCode && codeLines.length > 0) {
      items.push({ type: "code", text: codeLines.join("\n") });
    }

    return items;
  }, [content]);

  const normalizedQuickReplies = useMemo(() => {
    const raw = Array.isArray(quickReplies) ? quickReplies : [];
    const seen = new Set<string>();
    const out: string[] = [];
    for (const item of raw) {
      if (typeof item !== "string") continue;
      const cleaned = item.trim().replace(/\s+/g, " ");
      if (!cleaned) continue;
      const key = cleaned.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(cleaned);
      if (out.length >= 6) break;
    }
    return out;
  }, [quickReplies]);

  const normalizedClarifyingQuestions = useMemo(() => {
    const raw = Array.isArray(clarifyingQuestions) ? clarifyingQuestions : [];
    const seen = new Set<string>();
    const qrKeys = new Set(normalizedQuickReplies.map((t) => t.toLowerCase()));
    const out: string[] = [];
    for (const item of raw) {
      if (typeof item !== "string") continue;
      const cleaned = item.trim().replace(/\s+/g, " ");
      if (!cleaned) continue;
      const key = cleaned.toLowerCase();
      if (seen.has(key)) continue;
      if (qrKeys.has(key)) continue;
      seen.add(key);
      out.push(cleaned);
      if (out.length >= 6) break;
    }
    return out;
  }, [clarifyingQuestions, normalizedQuickReplies]);

  const hasMeta = Boolean(
    (typeof strategyUsed === "string" && strategyUsed.trim()) ||
      (typeof confidence === "string" && confidence.trim()) ||
      (typeof riskLevel === "string" && riskLevel.trim()) ||
      (searchQuality && typeof searchQuality === "object") ||
      (typeof disclaimer === "string" && disclaimer.trim()) ||
      (typeof strategyReason === "string" && strategyReason.trim())
  );

  const rate = async (value: number) => {
    if (!messageId) return;
    if (!localStorage.getItem("token")) {
      toast.info("登录后可评价");
      return;
    }
    rateMutation.mutate({ message_id: messageId, rating: value });
  };

  const copyTextToClipboard = async (text: string) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        toast.success("已复制到剪贴板");
        return;
      }

      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      textarea.style.top = "-9999px";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(textarea);

      if (ok) {
        toast.success("已复制到剪贴板");
      } else {
        toast.error("复制失败");
      }
    } catch {
      toast.error("复制失败");
    }
  };

  const copyToClipboard = async () => {
    await copyTextToClipboard(content);
  };

  const copyWithReferences = async () => {
    const parts: string[] = [];
    parts.push(String(content ?? ""));
    const refs = Array.isArray(references) ? references : [];
    if (refs.length > 0) {
      parts.push("\n\n相关法条：");
      for (const ref of refs) {
        const lawName = String(ref?.law_name ?? "").trim();
        const article = String(ref?.article ?? "").trim();
        const refContent = String(ref?.content ?? "").trim();
        const title = lawName || article ? `《${lawName}》${article}` : "法条引用";
        parts.push(`- ${title}`);
        if (refContent) {
          parts.push(refContent);
        }
        parts.push("");
      }
    }
    await copyTextToClipboard(parts.join("\n").trim());
  };

  const renderedBlocks = useMemo(() => {
    const nodes: ReactNode[] = [];
    let listItems: ReactNode[] = [];
    let orderedItems: ReactNode[] = [];

    const renderInline = (text: string): ReactNode => {
      const nodes: ReactNode[] = [];

      const escapeRegExp = (s: string) =>
        s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const buildLoose = (s: string) => {
        const compact = String(s ?? "").replace(/\s+/g, "");
        return compact
          .split("")
          .map((ch) => `${escapeRegExp(ch)}\\s*`)
          .join("")
          .replace(/\\s\*$/, "");
      };

      const patterns = (references ?? [])
        .map((ref) => {
          const lawName = String(ref.law_name ?? "").trim();
          const article = String(ref.article ?? "").trim();
          if (!lawName || !article) return null;
          const re = new RegExp(
            `《\\s*${buildLoose(lawName)}\\s*》\\s*${buildLoose(article)}`
          );
          return { ref, re };
        })
        .filter(Boolean) as Array<{ ref: LawReference; re: RegExp }>;

      const parseLawRefs = (
        segment: string,
        keyPrefix: string
      ): ReactNode[] => {
        if (!patterns.length) return [segment];
        const out: ReactNode[] = [];
        let remaining = segment;
        let guard = 0;

        while (remaining && guard < 200) {
          guard += 1;
          let best:
            | {
                index: number;
                match: string;
                ref: LawReference;
              }
            | undefined;

          for (const p of patterns) {
            const m = p.re.exec(remaining);
            if (!m) continue;
            if (!best || m.index < best.index) {
              best = { index: m.index, match: m[0], ref: p.ref };
            }
          }

          if (!best) {
            out.push(remaining);
            break;
          }

          if (best.index > 0) {
            out.push(remaining.slice(0, best.index));
          }
          if (!best.match) {
            out.push(remaining);
            break;
          }

          out.push(
            <button
              key={`${keyPrefix}-law-${guard}-${best.index}`}
              type="button"
              onClick={() => setActiveRef(best.ref)}
              className="inline-flex items-center text-blue-700 hover:text-blue-800 underline underline-offset-2 decoration-dotted dark:text-blue-300 dark:hover:text-blue-200"
            >
              {best.match}
            </button>
          );

          remaining = remaining.slice(best.index + best.match.length);
        }

        if (guard >= 200) {
          out.push(remaining);
        }

        return out;
      };

      const renderItalic = (
        segment: string,
        keyPrefix: string
      ): ReactNode[] => {
        const out: ReactNode[] = [];
        const emRe = /\*([^*]+)\*/g;
        let last = 0;
        let idx = 0;
        let m: RegExpExecArray | null;
        while ((m = emRe.exec(segment)) !== null) {
          if (m.index > last) {
            out.push(
              ...parseLawRefs(
                segment.slice(last, m.index),
                `${keyPrefix}-t-${idx}`
              )
            );
          }
          out.push(
            <em key={`${keyPrefix}-em-${idx}`} className="italic">
              {parseLawRefs(m[1], `${keyPrefix}-em-${idx}`)}
            </em>
          );
          last = m.index + m[0].length;
          idx += 1;
        }
        if (last < segment.length) {
          out.push(...parseLawRefs(segment.slice(last), `${keyPrefix}-tail`));
        }
        return out;
      };

      const pushFormatted = (segment: string, keyPrefix: string) => {
        const boldRe = /\*\*([^*]+)\*\*/g;
        let lastBold = 0;
        let idx = 0;
        let m: RegExpExecArray | null;
        while ((m = boldRe.exec(segment)) !== null) {
          if (m.index > lastBold) {
            nodes.push(
              ...renderItalic(
                segment.slice(lastBold, m.index),
                `${keyPrefix}-t-${idx}`
              )
            );
          }
          nodes.push(
            <strong
              key={`${keyPrefix}-b-${idx}`}
              className="font-semibold text-slate-900 dark:text-white"
            >
              {parseLawRefs(m[1], `${keyPrefix}-b-${idx}`)}
            </strong>
          );
          lastBold = m.index + m[0].length;
          idx += 1;
        }
        if (lastBold < segment.length) {
          nodes.push(
            ...renderItalic(segment.slice(lastBold), `${keyPrefix}-tail`)
          );
        }
      };

      const codeRe = /`([^`]+)`/g;
      let lastIndex = 0;
      let seg = 0;
      let m: RegExpExecArray | null;
      while ((m = codeRe.exec(text)) !== null) {
        if (m.index > lastIndex) {
          pushFormatted(text.slice(lastIndex, m.index), `seg-${seg}`);
          seg += 1;
        }
        nodes.push(
          <code
            key={`code-${m.index}`}
            className="px-1.5 py-0.5 rounded-md bg-slate-100 border border-slate-200 font-mono text-[12px] text-slate-900 dark:bg-slate-700 dark:border-slate-600 dark:text-slate-200"
          >
            {m[1]}
          </code>
        );
        lastIndex = m.index + m[0].length;
      }
      if (lastIndex < text.length) {
        pushFormatted(text.slice(lastIndex), `seg-${seg}`);
      }

      return <>{nodes}</>;
    };

    const flushList = (keySuffix: string) => {
      if (listItems.length > 0) {
        nodes.push(
          <ul
            key={`ul-${keySuffix}`}
            className="space-y-1 pl-5 list-disc marker:text-slate-400"
          >
            {listItems}
          </ul>
        );
        listItems = [];
      }
    };

    const flushOrdered = (keySuffix: string) => {
      if (orderedItems.length > 0) {
        nodes.push(
          <ol
            key={`ol-${keySuffix}`}
            className="space-y-1 pl-5 list-decimal marker:text-slate-400"
          >
            {orderedItems}
          </ol>
        );
        orderedItems = [];
      }
    };

    blocks.forEach((b, idx) => {
      if (b.type === "li") {
        listItems.push(
          <li key={`li-${idx}`} className="">
            <p className="whitespace-pre-wrap">{renderInline(b.text)}</p>
          </li>
        );
        return;
      }

      if (b.type === "oli") {
        orderedItems.push(
          <li key={`oli-${idx}`} className="">
            <p className="whitespace-pre-wrap">{renderInline(b.text)}</p>
          </li>
        );
        return;
      }

      flushList(String(idx));
      flushOrdered(String(idx));

      if (b.type === "br") {
        nodes.push(<div key={`br-${idx}`} className="h-2" />);
        return;
      }

      if (b.type === "code") {
        nodes.push(
          <pre
            key={`codeblock-${idx}`}
            className="rounded-xl bg-slate-100 border border-slate-200 overflow-x-auto p-4 text-[12px] leading-relaxed font-mono text-slate-800 dark:bg-slate-900 dark:border-slate-700 dark:text-slate-200"
          >
            <code>{b.text}</code>
          </pre>
        );
        return;
      }

      if (b.type === "h2") {
        nodes.push(
          <h2
            key={`h2-${idx}`}
            className="text-base font-bold text-slate-900 dark:text-white tracking-tight mt-4 first:mt-0"
          >
            {b.text}
          </h2>
        );
        return;
      }

      if (b.type === "h3") {
        nodes.push(
          <h3
            key={`h3-${idx}`}
            className="text-sm font-semibold text-slate-900 dark:text-white mt-4 first:mt-0 flex items-center gap-2"
          >
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500" />
            {b.text}
          </h3>
        );
        return;
      }

      if (b.type === "quote") {
        nodes.push(
          <div
            key={`quote-${idx}`}
            className="border-l-4 border-blue-500 bg-blue-50/50 rounded-r-xl px-4 py-3 text-sm text-slate-700 dark:bg-blue-900/20 dark:text-slate-300"
          >
            <p className="whitespace-pre-wrap">{renderInline(b.text)}</p>
          </div>
        );
        return;
      }

      nodes.push(
        <p key={`p-${idx}`} className="whitespace-pre-wrap">
          {renderInline(b.text)}
        </p>
      );
    });

    flushList("end");
    flushOrdered("end");
    return nodes;
  }, [blocks, references]);

  return (
    <div className="space-y-4">
      <Modal
        isOpen={activeRef != null}
        onClose={() => setActiveRef(null)}
        title={
          activeRef
            ? `《${String(activeRef.law_name ?? "")}》${String(
                activeRef.article ?? ""
              )}`
            : undefined
        }
        size="lg"
      >
        <div className="space-y-4">
          <div className="text-sm leading-relaxed text-slate-700 dark:text-slate-200 whitespace-pre-wrap">
            {activeRef?.content}
          </div>
          {typeof activeRef?.relevance === "number" && (
            <div className="text-xs text-slate-500 dark:text-slate-400">
              关联度 {Math.round(activeRef.relevance * 100)}%
            </div>
          )}
        </div>
      </Modal>

      <ThinkingProcess steps={thinkingSteps} isThinking={Boolean(isThinking)} />

      {(!content || content.trim().length === 0) && isStreaming ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <span className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-bounce" />
          <span
            className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-bounce"
            style={{ animationDelay: "0.1s" }}
          />
          <span
            className="inline-block w-2 h-2 rounded-full bg-blue-500 animate-bounce"
            style={{ animationDelay: "0.2s" }}
          />
        </div>
      ) : (
        <div className="space-y-3 text-[15px] leading-7">{renderedBlocks}</div>
      )}

      {hasMeta && (
        <div className="pt-1">
          <button
            type="button"
            onClick={() => setShowMeta((v) => !v)}
            className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <Info className="h-3.5 w-3.5" />
            <span>回答信息</span>
            {showMeta ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>
          {showMeta && (
            <div className="mt-2 space-y-2 rounded-xl bg-slate-50 border border-slate-200 p-3 text-xs text-slate-600 dark:bg-slate-800/50 dark:border-slate-700 dark:text-slate-300">
              {typeof strategyUsed === "string" && strategyUsed.trim() && (
                <div>
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    策略
                  </span>
                  <span className="ml-2">{strategyUsed.trim()}</span>
                </div>
              )}
              {typeof strategyReason === "string" && strategyReason.trim() && (
                <div>
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    原因
                  </span>
                  <span className="ml-2 whitespace-pre-wrap">
                    {strategyReason.trim()}
                  </span>
                </div>
              )}
              {typeof confidence === "string" && confidence.trim() && (
                <div>
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    置信度
                  </span>
                  <span className="ml-2">{confidence.trim()}</span>
                </div>
              )}
              {typeof riskLevel === "string" && riskLevel.trim() && (
                <div>
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    风险
                  </span>
                  <span className="ml-2">{riskLevel.trim()}</span>
                </div>
              )}
              {searchQuality && typeof searchQuality === "object" && (
                <div>
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    检索质量
                  </span>
                  <span className="ml-2">
                    候选 {Number(searchQuality.total_candidates ?? 0)}，通过
                    {" "}
                    {Number(searchQuality.qualified_count ?? 0)}，平均相似度
                    {" "}
                    {Number(searchQuality.avg_similarity ?? 0).toFixed(3)}，置信
                    {" "}
                    {String(searchQuality.confidence ?? "")}
                  </span>
                </div>
              )}
              {typeof disclaimer === "string" && disclaimer.trim() && (
                <div>
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    免责声明
                  </span>
                  <div className="mt-1 whitespace-pre-wrap">
                    {disclaimer.trim()}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {normalizedQuickReplies.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {normalizedQuickReplies.map((text, idx) => (
              <button
                key={`qr-${idx}`}
                type="button"
                onClick={() => onQuickReplySelect?.(String(text))}
                className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 transition-colors dark:bg-slate-800/60 dark:hover:bg-slate-800 dark:text-slate-200 dark:border-slate-700"
              >
                {String(text)}
              </button>
            ))}
        </div>
      )}

      {normalizedClarifyingQuestions.length > 0 && (
        <div className="pt-1">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
            <Lightbulb className="h-3.5 w-3.5" />
            <span>建议追问</span>
            {typeof intent === "string" && intent.trim() && (
              <span className="px-2 py-0.5 rounded-full text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-900/20 dark:text-indigo-200 dark:border-indigo-800">
                {intent.trim()}
              </span>
            )}
          </div>
          {needsClarification === true && (
            <div className="mt-2 rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-700 dark:border-indigo-800 dark:bg-indigo-900/20 dark:text-indigo-200">
              为了更准确判断，请补充以下信息（可直接点选）：
            </div>
          )}
          <div className="flex flex-wrap gap-2 pt-2">
            {normalizedClarifyingQuestions.map((text, idx) => (
                <button
                  key={`cq-${idx}`}
                  type="button"
                  onClick={() => onQuickReplySelect?.(String(text))}
                  className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition-colors dark:bg-indigo-900/20 dark:hover:bg-indigo-900/30 dark:text-indigo-200 dark:border-indigo-800"
                >
                  {String(text)}
                </button>
              ))}
          </div>
        </div>
      )}

      <MessageActionsBar
        disabled={Boolean(isStreaming)}
        canCopy={Boolean(String(content ?? "").trim())}
        canFavorite={Boolean(messageId)}
        canRate={Boolean(messageId)}
        canRegenerate={Boolean(onRegenerate) && !isStreaming}
        favorited={favorited}
        rated={rated}
        rateLoading={rateMutation.isPending}
        onCopy={copyToClipboard}
        onCopyWithReferences={copyWithReferences}
        onToggleFavorite={toggleFavorite}
        onRateGood={() => rate(3)}
        onRateBad={() => rate(1)}
        onRegenerate={onRegenerate}
      />

      {references && references.length > 0 && (
        <div className="pt-2">
          <button
            onClick={() => setShowRefs(!showRefs)}
            className="flex items-center gap-2 text-xs font-medium text-blue-600 hover:text-blue-700 transition-colors px-3 py-1.5 bg-blue-50 rounded-lg hover:bg-blue-100 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 dark:text-blue-400"
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>相关法条 ({references.length})</span>
            {showRefs ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>

          {showRefs && (
            <div className="mt-3 space-y-2 animate-fade-in">
              {references.map((ref, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl bg-slate-50 border border-slate-100 dark:bg-slate-800/50 dark:border-slate-700"
                >
                  <div className="flex items-start gap-3">
                    <div className="p-1.5 bg-blue-100 rounded-lg dark:bg-blue-900/50">
                      <BookOpen className="h-4 w-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-slate-900 dark:text-white">
                        《{ref.law_name}》{ref.article}
                      </p>
                      <p className="text-sm text-slate-600 mt-1 leading-relaxed dark:text-slate-400">
                        {ref.content}
                      </p>
                      {ref.relevance && (
                        <div className="mt-2 flex items-center gap-2">
                          <div className="h-1.5 w-24 bg-slate-200 rounded-full overflow-hidden dark:bg-slate-700">
                            <div
                              className="h-full bg-blue-500 rounded-full"
                              style={{ width: `${ref.relevance * 100}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-400">
                            关联度 {Math.round(ref.relevance * 100)}%
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
