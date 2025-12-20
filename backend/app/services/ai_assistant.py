"""AI法律咨询助手服务"""
import uuid
import logging
import time
from typing import Any, cast

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.schemas.ai import LawReference

settings = get_settings()

logger = logging.getLogger(__name__)


class LegalKnowledgeBase:
    """法律知识库管理"""
    
    def __init__(self):
        self.embeddings = None
        self.vector_store: Chroma | None = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "；", " "]
        )
        self._initialized = False
    
    def initialize(self):
        """初始化或加载向量数据库"""
        if self._initialized:
            return
        
        try:
            if settings.openai_api_key:
                self.embeddings = OpenAIEmbeddings(
                    api_key=cast(Any, settings.openai_api_key),
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
        
        texts = []
        metadatas = []
        
        for doc in documents:
            content = f"【{str(doc.get('law_name', ''))}】{str(doc.get('article', ''))}\n{str(doc.get('content', ''))}"
            texts.append(content)
            metadatas.append({
                "law_name": str(doc.get('law_name', '')),
                "article": str(doc.get('article', '')),
                "source": str(doc.get('source', '')),
            })
        
        if texts and self.vector_store:
            self.vector_store.add_texts(texts=texts, metadatas=metadatas)
    
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
            return [(doc.page_content, doc.metadata, score) for doc, score in results]
        except Exception:
            logger.exception("搜索失败")
            return []


class AILegalAssistant:
    """AI法律咨询助手"""
    
    SYSTEM_PROMPT = """你是"百姓法律助手"的AI法律咨询员，专门为普通百姓提供法律咨询服务。

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
        self.llm = ChatOpenAI(
            model=settings.ai_model,
            api_key=cast(Any, settings.openai_api_key),
            base_url=settings.openai_base_url,
            temperature=0.7,
            max_completion_tokens=2000
        )
        self.knowledge_base = LegalKnowledgeBase()
        self.knowledge_base.initialize()
        self.conversation_histories: dict[str, list[dict[str, str]]] = {}
        self._last_seen: dict[str, float] = {}
        self._max_sessions = 5000
        self._max_messages_per_session = 50

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
            self.conversation_histories.pop(oldest_session, None)
            self._last_seen.pop(oldest_session, None)
    
    def _build_context(self, references: list[tuple[str, dict[str, object], float]]) -> str:
        """构建上下文字符串"""
        if not references:
            return "暂无相关法律条文参考，请基于你的法律知识回答。"
        
        context_parts = []
        for i, (content, metadata, score) in enumerate(references, 1):
            context_parts.append(f"{i}. {content}")
        
        return "\n\n".join(context_parts)
    
    def _parse_references(self, references: list[tuple[str, dict[str, object], float]]) -> list[LawReference]:
        """解析法律引用"""
        result = []
        for content, metadata, score in references:
            result.append(LawReference(
                law_name=str(metadata.get('law_name', '未知法律')),
                article=str(metadata.get('article', '未知条款')),
                content=content,
                relevance=round(1 - score, 2) if score < 1 else round(score, 2)
            ))
        return result
    
    def get_or_create_session(self, session_id: str | None = None) -> str:
        """获取或创建会话"""
        if session_id and session_id in self.conversation_histories:
            self._last_seen[session_id] = time.time()
            return session_id
        
        new_session_id = session_id or uuid.uuid4().hex
        self.conversation_histories[new_session_id] = []
        self._last_seen[new_session_id] = time.time()
        self._evict_if_needed()
        return new_session_id
    
    async def chat(
        self, 
        message: str, 
        session_id: str | None = None
    ) -> tuple[str, str, list[LawReference]]:
        """
        与AI助手对话
        
        Args:
            message: 用户消息
            session_id: 会话ID
            
        Returns:
            (session_id, answer, references)
        """
        session_id = self.get_or_create_session(session_id)
        
        references = self.knowledge_base.search(message, k=5)
        context = self._build_context(references)
        
        history = self.conversation_histories.get(session_id, [])
        
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
        
        history.append({'role': 'user', 'content': message})
        history.append({'role': 'assistant', 'content': answer})
        self.conversation_histories[session_id] = history[-self._max_messages_per_session:]
        self._last_seen[session_id] = time.time()
        self._evict_if_needed()
        
        parsed_refs = self._parse_references(references)
        
        return session_id, answer, parsed_refs
    
    def clear_session(self, session_id: str):
        """清除会话历史"""
        if session_id in self.conversation_histories:
            del self.conversation_histories[session_id]
        self._last_seen.pop(session_id, None)
    
    async def chat_stream(
        self, 
        message: str, 
        session_id: str | None = None
    ):
        """
        流式对话
        
        Args:
            message: 用户消息
            session_id: 会话ID
            
        Yields:
            (event_type, data) - 事件类型和数据
        """
        session_id = self.get_or_create_session(session_id)
        
        references = self.knowledge_base.search(message, k=5)
        context = self._build_context(references)
        parsed_refs = self._parse_references(references)
        
        # 先发送session_id和引用
        yield ("session", {"session_id": session_id})
        yield ("references", {"references": [ref.model_dump() for ref in parsed_refs]})
        
        history = self.conversation_histories.get(session_id, [])
        
        messages: list[BaseMessage] = [
            SystemMessage(content=self.SYSTEM_PROMPT.format(context=context))
        ]
        
        for msg in history[-10:]:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            else:
                messages.append(AIMessage(content=msg['content']))
        
        messages.append(HumanMessage(content=message))
        
        full_answer = ""
        try:
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    content = str(chunk.content)
                    full_answer += content
                    yield ("content", {"text": content})
        except Exception:
            logger.exception("AI服务调用失败")
            error_msg = "抱歉，AI服务暂时不可用。"
            yield ("content", {"text": error_msg})
            full_answer = error_msg
        
        # 更新历史
        history.append({'role': 'user', 'content': message})
        history.append({'role': 'assistant', 'content': full_answer})
        self.conversation_histories[session_id] = history[-self._max_messages_per_session:]
        self._last_seen[session_id] = time.time()
        self._evict_if_needed()
        
        yield ("done", {"session_id": session_id})


_ai_assistant = None


def get_ai_assistant() -> AILegalAssistant:
    """获取AI助手实例（懒加载）"""
    global _ai_assistant
    if _ai_assistant is None:
        _ai_assistant = AILegalAssistant()
    return _ai_assistant
