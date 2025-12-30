"""AI法律咨询助手服务"""
import uuid
import logging
import time
from collections.abc import AsyncGenerator
from typing import cast

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import SecretStr

from ..config import get_settings
from ..schemas.ai import LawReference
from .ai_response_strategy import ResponseStrategy, ResponseStrategyDecider, SearchQuality
from .content_safety import ContentSafetyFilter, RiskLevel
from .disclaimer import DisclaimerManager

settings = get_settings()

logger = logging.getLogger(__name__)


class LegalKnowledgeBase:
    """法律知识库管理"""

    RELEVANCE_THRESHOLD: float = 0.75
    MIN_REFERENCES: int = 1
    MAX_REFERENCES: int = 5
    
    def __init__(self):
        self.embeddings: OpenAIEmbeddings | None = None
        self.vector_store: Chroma | None = None
        self.text_splitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "；", " "]
        )
        self._initialized: bool = False
    
    def initialize(self):
        """初始化或加载向量数据库"""
        if self._initialized:
            return
        
        try:
            if settings.openai_api_key:
                self.embeddings = OpenAIEmbeddings(
                    api_key=SecretStr(settings.openai_api_key),
                    base_url=settings.openai_base_url
                )
                self.vector_store = Chroma(
                    persist_directory=settings.chroma_persist_dir,
                    embedding_function=self.embeddings,
                    collection_name="legal_knowledge"
                )
            self._initialized = True
        except Exception:
            logger.exception("初始化向量数据库失败")
            self._initialized = True
    
    def add_law_documents(self, documents: list[dict[str, object]]):
        """添加法律文档到知识库
        
        Args:
            documents: 法律文档列表，每个文档包含 law_name, article, content
        """
        if not self.vector_store:
            self.initialize()
        
        texts: list[str] = []
        metadatas: list[dict[str, str]] = []
        
        for doc in documents:
            content = f"【{str(doc.get('law_name', ''))}】{str(doc.get('article', ''))}\n{str(doc.get('content', ''))}"
            texts.append(content)
            metadatas.append({
                "law_name": str(doc.get('law_name', '')),
                "article": str(doc.get('article', '')),
                "source": str(doc.get('source', '')),
            })
        
        if texts and self.vector_store:
            add_texts = getattr(self.vector_store, "add_texts", None)
            if callable(add_texts):
                _ = add_texts(texts=texts, metadatas=metadatas)
    
    def search(self, query: str, k: int = 5) -> list[tuple[str, dict[str, object], float]]:
        """搜索相关法律条文
        
        Args:
            query: 查询文本
            k: 返回结果数量
            
        Returns:
            List of (content, metadata, score)
        """
        if not self.vector_store:
            self.initialize()

        if self.vector_store is None:
            return []
        
        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)
            packed: list[tuple[str, dict[str, object], float]] = []
            for doc, score in results:
                doc_obj = cast(object, doc)
                content = str(getattr(doc_obj, "page_content", ""))
                metadata_raw = getattr(doc_obj, "metadata", {})
                if not isinstance(metadata_raw, dict):
                    metadata_raw = {}
                similarity = self._score_to_similarity(float(score))
                packed.append((content, cast(dict[str, object], metadata_raw), similarity))
            return packed
        except Exception:
            logger.exception("搜索失败")
            return []

    def search_with_quality_control(
        self,
        query: str,
        *,
        k: int = 5,
        threshold: float | None = None,
    ) -> tuple[list[tuple[str, dict[str, object], float]], SearchQuality]:
        th = float(self.RELEVANCE_THRESHOLD if threshold is None else threshold)

        candidates = self.search(query, k=k)
        filtered = [r for r in candidates if float(r[2]) >= th]
        filtered = filtered[: int(self.MAX_REFERENCES)]

        if filtered:
            avg_similarity = sum(float(r[2]) for r in filtered) / float(len(filtered))
        else:
            avg_similarity = 0.0

        confidence = self._calculate_confidence(filtered)
        return (
            filtered,
            SearchQuality(
                total_candidates=len(candidates),
                qualified_count=len(filtered),
                avg_similarity=float(avg_similarity),
                confidence=str(confidence),
            ),
        )

    def _calculate_confidence(self, results: list[tuple[str, dict[str, object], float]]) -> str:
        if not results:
            return "low"
        avg = sum(float(r[2]) for r in results) / float(len(results))
        if avg >= 0.85 and len(results) >= 2:
            return "high"
        if avg >= 0.7:
            return "medium"
        return "low"

    def _score_to_similarity(self, score: float) -> float:
        if score <= 0:
            return 1.0
        if score <= 1:
            sim = 1.0 - score
        else:
            sim = 1.0 / (1.0 + score)
        if sim < 0:
            return 0.0
        if sim > 1:
            return 1.0
        return float(sim)


class AILegalAssistant:
    """AI法律咨询助手"""

    SYSTEM_PROMPT: str = """你是"百姓法律助手"的AI法律咨询员，专门为普通百姓提供法律咨询服务。

## 你的核心职责：
1. 基于中国法律法规，为用户提供准确、专业的法律咨询
2. 用通俗易懂的语言解释法律概念
3. **精准引用法条**：回答时必须引用具体的法律条文作为依据
4. 对于复杂案件，建议用户寻求专业律师帮助

## 回答格式规范（必须严格遵守）：

### 1. 问题理解
首先简要概括用户的法律问题和核心诉求。

### 2. 法律分析
结合相关法律条文进行详细分析，使用以下格式引用法条：
> 📜 **《法律名称》第X条**：具体条文内容

### 3. 风险评估
根据用户描述的情况，给出风险等级评估：
- 🟢 **低风险**：法律关系明确，胜诉可能性较高
- 🟡 **中风险**：存在争议点，需要补充证据
- 🔴 **高风险**：法律依据不足或对方占优势

### 4. 行动建议
给出具体、可操作的建议步骤。

### 5. 追问确认（如需要）
如果信息不足以给出准确建议，使用以下格式追问：
❓ **为了更好地帮助您，请补充以下信息：**
1. [具体问题1]
2. [具体问题2]

## 智能追问场景：
当用户描述以下情况时，主动追问关键信息：
- 劳动纠纷：是否签订劳动合同？工作年限？是否有证据？
- 婚姻家庭：婚姻状况？财产情况？子女抚养意愿？
- 合同纠纷：合同是否书面？违约条款？损失金额？
- 交通事故：责任认定书？保险情况？伤亡程度？
- 借贷纠纷：是否有借条？金额？还款期限？

## 注意事项：
- 如果问题不在你的知识范围内，诚实告知用户
- 对于涉及人身安全的紧急情况，提醒用户及时报警（110）
- 不要提供任何违法建议
- 对于刑事案件，强烈建议聘请专业律师
- 涉及金额超过10万元的案件，建议咨询专业律师

## 相关法律参考：
{context}

请基于以上信息和格式规范回答用户的问题。"""

    def __init__(self):
        self.llm: ChatOpenAI = ChatOpenAI(
            model=settings.ai_model,
            api_key=SecretStr(settings.openai_api_key),
            base_url=settings.openai_base_url,
            temperature=0.7,
            model_kwargs={"max_completion_tokens": 2000},
        )
        self.knowledge_base: LegalKnowledgeBase = LegalKnowledgeBase()
        self.knowledge_base.initialize()
        self.safety_filter: ContentSafetyFilter = ContentSafetyFilter()
        self.strategy_decider: ResponseStrategyDecider = ResponseStrategyDecider()
        self.disclaimer_manager: DisclaimerManager = DisclaimerManager()
        self.conversation_histories: dict[str, list[dict[str, str]]] = {}
        self._last_seen: dict[str, float] = {}
        self._max_sessions: int = 5000
        self._max_messages_per_session: int = 50

    def _evict_if_needed(self) -> None:
        if len(self.conversation_histories) <= self._max_sessions:
            return

        oldest_session: str | None = None
        oldest_time = float("inf")
        for sid, ts in self._last_seen.items():
            if ts < oldest_time:
                oldest_time = ts
                oldest_session = sid

        if oldest_session is not None:
            _ = self.conversation_histories.pop(oldest_session, None)
            _ = self._last_seen.pop(oldest_session, None)
    
    def _build_context(self, references: list[tuple[str, dict[str, object], float]]) -> str:
        """构建上下文字符串"""
        if not references:
            return "暂无相关法律条文参考，请基于你的法律知识回答。"
        
        context_parts: list[str] = []
        for i, (content, _metadata, _score) in enumerate(references, 1):
            context_parts.append(f"{i}. {content}")
        
        return "\n\n".join(context_parts)
    
    def _parse_references(self, references: list[tuple[str, dict[str, object], float]]) -> list[LawReference]:
        """解析法律引用"""
        result: list[LawReference] = []
        for content, metadata, score in references:
            result.append(LawReference(
                law_name=str(metadata.get('law_name', '未知法律')),
                article=str(metadata.get('article', '未知条款')),
                content=content,
                relevance=round(float(score), 2)
            ))
        return result

    def _append_disclaimer(self, answer: str, *, risk_level: RiskLevel, strategy: ResponseStrategy) -> str:
        disclaimer = self.disclaimer_manager.get_disclaimer(risk_level=risk_level, strategy=strategy)
        if not str(disclaimer or "").strip():
            return answer

        if "仅供参考" in str(answer):
            return answer
        return str(answer) + str(disclaimer)

    def _normalize_history(self, history: list[dict[str, str]]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in history:
            role = str(item.get("role", "")).strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            normalized.append({"role": role, "content": content})

        if not normalized:
            return []
        return normalized[-self._max_messages_per_session:]
    
    def get_or_create_session(
        self,
        session_id: str | None = None,
        *,
        initial_history: list[dict[str, str]] | None = None,
    ) -> str:
        """获取或创建会话

        - 当服务重启后，如果传入了旧的 session_id，本方法允许用 initial_history
          （通常来自 DB）为该 session 进行一次性补种，以保证上下文连续。
        """
        if session_id and session_id in self.conversation_histories:
            self._last_seen[session_id] = time.time()
            return session_id

        new_session_id = session_id or uuid.uuid4().hex
        if new_session_id not in self.conversation_histories:
            self.conversation_histories[new_session_id] = []

        existing = self.conversation_histories.get(new_session_id, [])
        if (not existing) and initial_history:
            self.conversation_histories[new_session_id] = self._normalize_history(initial_history)

        self._last_seen[new_session_id] = time.time()
        self._evict_if_needed()
        return new_session_id

    def clear_session(self, session_id: str) -> None:
        _ = self.conversation_histories.pop(str(session_id), None)
        _ = self._last_seen.pop(str(session_id), None)
    
    async def chat(
        self, 
        message: str, 
        session_id: str | None = None,
        *,
        initial_history: list[dict[str, str]] | None = None,
    ) -> tuple[str, str, list[LawReference], dict[str, object]]:
        """
        与AI助手对话
        
        Args:
            message: 用户消息
            session_id: 会话ID
            
        Returns:
            (session_id, answer, references)
        """
        session_id = self.get_or_create_session(session_id, initial_history=initial_history)

        safety = self.safety_filter.check_input(message)
        if safety.risk_level == RiskLevel.BLOCKED:
            strategy = ResponseStrategy.REFUSE_ANSWER
            disclaimer = self.disclaimer_manager.get_disclaimer(risk_level=safety.risk_level, strategy=strategy)

            answer = str(safety.suggestion or "很抱歉，我无法回答这类问题。如需帮助，请联系专业机构。")
            answer = self._append_disclaimer(answer, risk_level=safety.risk_level, strategy=strategy)
            answer = self.safety_filter.sanitize_output(answer)

            history = self.conversation_histories.get(session_id, [])
            history.append({'role': 'user', 'content': message})
            history.append({'role': 'assistant', 'content': answer})
            self.conversation_histories[session_id] = history[-self._max_messages_per_session:]
            self._last_seen[session_id] = time.time()
            self._evict_if_needed()

            meta: dict[str, object] = {
                "strategy_used": str(strategy.value),
                "strategy_reason": "内容安全拦截",
                "confidence": "N/A",
                "risk_level": str(safety.risk_level.value),
                "search_quality": {
                    "total_candidates": 0,
                    "qualified_count": 0,
                    "avg_similarity": 0.0,
                    "confidence": "low",
                },
                "disclaimer": str(disclaimer),
            }
            return session_id, answer, [], meta

        references, quality = self.knowledge_base.search_with_quality_control(message, k=5)
        decision = self.strategy_decider.decide(message, quality, risk_level=safety.risk_level)
        disclaimer = self.disclaimer_manager.get_disclaimer(risk_level=safety.risk_level, strategy=decision.strategy)
        context = self._build_context(references)

        history = self.conversation_histories.get(session_id, [])

        answer: str
        if decision.strategy == ResponseStrategy.REDIRECT:
            answer = "您的问题可能涉及较高风险或需要结合具体案情，建议您尽快咨询专业律师获取针对性意见。"
        elif decision.strategy == ResponseStrategy.REFUSE_ANSWER:
            answer = str(safety.suggestion or "很抱歉，我无法回答这类问题。")
        else:
            messages: list[BaseMessage] = [
                SystemMessage(content=self.SYSTEM_PROMPT.format(context=context))
            ]

            for msg in history[-10:]:
                if msg['role'] == 'user':
                    messages.append(HumanMessage(content=msg['content']))
                else:
                    messages.append(AIMessage(content=msg['content']))

            messages.append(HumanMessage(content=message))

            try:
                response = await self.llm.agenerate([messages])
                answer = response.generations[0][0].text
            except Exception:
                logger.exception("AI服务调用失败")
                answer = "抱歉，AI服务暂时不可用。您可以稍后重试，或直接联系我们的在线律师获取帮助。"

        answer = self._append_disclaimer(answer, risk_level=safety.risk_level, strategy=decision.strategy)
        answer = self.safety_filter.sanitize_output(answer)
        
        history.append({'role': 'user', 'content': message})
        history.append({'role': 'assistant', 'content': answer})
        self.conversation_histories[session_id] = history[-self._max_messages_per_session:]
        self._last_seen[session_id] = time.time()
        self._evict_if_needed()
        
        parsed_refs = self._parse_references(references)

        meta2: dict[str, object] = {
            "strategy_used": str(decision.strategy.value),
            "strategy_reason": str(decision.reason),
            "confidence": str(decision.confidence),
            "risk_level": str(safety.risk_level.value),
            "search_quality": {
                "total_candidates": int(quality.total_candidates),
                "qualified_count": int(quality.qualified_count),
                "avg_similarity": float(quality.avg_similarity),
                "confidence": str(quality.confidence),
            },
            "disclaimer": str(disclaimer),
        }
        
        return session_id, answer, parsed_refs, meta2
    
    async def chat_stream(
        self, 
        message: str, 
        session_id: str | None = None,
        *,
        initial_history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[tuple[str, dict[str, object]], None]:
        """
        流式对话
        
        Args:
            message: 用户消息
            session_id: 会话ID
            
        Yields:
            (event_type, data) - 事件类型和数据
        """
        session_id = self.get_or_create_session(session_id, initial_history=initial_history)

        safety = self.safety_filter.check_input(message)
        if safety.risk_level == RiskLevel.BLOCKED:
            strategy = ResponseStrategy.REFUSE_ANSWER
            disclaimer = self.disclaimer_manager.get_disclaimer(risk_level=safety.risk_level, strategy=strategy)
            yield ("session", {"session_id": session_id})
            yield ("references", {"references": []})
            yield (
                "meta",
                {
                    "strategy_used": str(strategy.value),
                    "strategy_reason": "内容安全拦截",
                    "confidence": "N/A",
                    "risk_level": str(safety.risk_level.value),
                    "search_quality": {
                        "total_candidates": 0,
                        "qualified_count": 0,
                        "avg_similarity": 0.0,
                        "confidence": "low",
                    },
                    "disclaimer": str(disclaimer),
                },
            )

            full_answer = str(safety.suggestion or "很抱歉，我无法回答这类问题。如需帮助，请联系专业机构。")
            full_answer = self._append_disclaimer(
                full_answer,
                risk_level=safety.risk_level,
                strategy=strategy,
            )
            full_answer = self.safety_filter.sanitize_output(full_answer)
            yield ("content", {"text": full_answer})

            history = self.conversation_histories.get(session_id, [])
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": full_answer})
            self.conversation_histories[session_id] = history[-self._max_messages_per_session:]
            self._last_seen[session_id] = time.time()
            self._evict_if_needed()
            yield (
                "done",
                {
                    "session_id": session_id,
                    "strategy_used": str(strategy.value),
                    "strategy_reason": "内容安全拦截",
                    "confidence": "N/A",
                    "risk_level": str(safety.risk_level.value),
                },
            )
            return

        references, quality = self.knowledge_base.search_with_quality_control(message, k=5)
        decision = self.strategy_decider.decide(message, quality, risk_level=safety.risk_level)
        disclaimer = self.disclaimer_manager.get_disclaimer(risk_level=safety.risk_level, strategy=decision.strategy)
        context = self._build_context(references)
        parsed_refs = self._parse_references(references)

        yield ("session", {"session_id": session_id})
        yield ("references", {"references": [ref.model_dump() for ref in parsed_refs]})
        yield (
            "meta",
            {
                "strategy_used": str(decision.strategy.value),
                "strategy_reason": str(decision.reason),
                "confidence": str(decision.confidence),
                "risk_level": str(safety.risk_level.value),
                "search_quality": {
                    "total_candidates": int(quality.total_candidates),
                    "qualified_count": int(quality.qualified_count),
                    "avg_similarity": float(quality.avg_similarity),
                    "confidence": str(quality.confidence),
                },
                "disclaimer": str(disclaimer),
            },
        )

        history = self.conversation_histories.get(session_id, [])

        messages: list[BaseMessage] = [
            SystemMessage(content=self.SYSTEM_PROMPT.format(context=context))
        ]

        for msg in history[-10:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=message))

        full_answer = ""

        if decision.strategy == ResponseStrategy.REDIRECT:
            full_answer = "您的问题可能涉及较高风险或需要结合具体案情，建议您尽快咨询专业律师获取针对性意见。"
            full_answer = self._append_disclaimer(
                full_answer,
                risk_level=safety.risk_level,
                strategy=decision.strategy,
            )
            full_answer = self.safety_filter.sanitize_output(full_answer)
            yield ("content", {"text": full_answer})
        elif decision.strategy == ResponseStrategy.REFUSE_ANSWER:
            full_answer = str(safety.suggestion or "很抱歉，我无法回答这类问题。")
            full_answer = self._append_disclaimer(
                full_answer,
                risk_level=safety.risk_level,
                strategy=decision.strategy,
            )
            full_answer = self.safety_filter.sanitize_output(full_answer)
            yield ("content", {"text": full_answer})
        else:
            try:
                async for chunk in self.llm.astream(messages):
                    raw = cast(object | None, getattr(chunk, "content", None))
                    if raw is None:
                        continue
                    if isinstance(raw, str):
                        content = raw
                    elif isinstance(raw, list):
                        content = "".join(str(item) for item in cast(list[object], raw))
                    else:
                        content = str(raw)
                    if not content:
                        continue
                    content = self.safety_filter.sanitize_output(content)
                    full_answer += content
                    yield ("content", {"text": content})
            except Exception:
                logger.exception("AI服务调用失败")
                error_msg = "抱歉，AI服务暂时不可用。"
                error_msg = self.safety_filter.sanitize_output(error_msg)
                full_answer = error_msg
                yield ("content", {"text": error_msg})

            with_disclaimer = self._append_disclaimer(
                full_answer,
                risk_level=safety.risk_level,
                strategy=decision.strategy,
            )
            if with_disclaimer.startswith(full_answer):
                suffix = with_disclaimer[len(full_answer) :]
                suffix = self.safety_filter.sanitize_output(suffix)
                if suffix:
                    full_answer += suffix
                    yield ("content", {"text": suffix})
            else:
                full_answer = self.safety_filter.sanitize_output(with_disclaimer)

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": full_answer})
        self.conversation_histories[session_id] = history[-self._max_messages_per_session:]
        self._last_seen[session_id] = time.time()
        self._evict_if_needed()

        yield (
            "done",
            {
                "session_id": session_id,
                "strategy_used": str(decision.strategy.value),
                "strategy_reason": str(decision.reason),
                "confidence": str(decision.confidence),
                "risk_level": str(safety.risk_level.value),
            },
        )


_ai_assistant = None


def get_ai_assistant() -> AILegalAssistant:
    """获取AI助手实例（懒加载）"""
    global _ai_assistant
    if _ai_assistant is None:
        _ai_assistant = AILegalAssistant()
    return _ai_assistant
