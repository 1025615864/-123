AI 咨询模块增强建议与规划
基于你当前的实现情况和已知限制，我从 技术架构、RAG 质量、用户体验、安全合规、可观测性、业务扩展 六个维度给出详细建议。

一、RAG 质量与可控性增强（优先级：🔴 高）
1.1 检索质量控制
问题：当前仅做 k=5 相似度检索，缺少质量阈值控制

Python

# backend/app/services/ai_assistant.py 建议增强

class LegalKnowledgeBase: # 新增配置
RELEVANCE_THRESHOLD = 0.75 # 相似度阈值
MIN_REFERENCES = 1 # 最少引用数
MAX_REFERENCES = 5 # 最多引用数

    def search_with_quality_control(
        self,
        query: str,
        k: int = 5,
        threshold: float = None
    ) -> tuple[list, SearchQuality]:
        """带质量控制的检索"""
        threshold = threshold or self.RELEVANCE_THRESHOLD
        results = self.vectorstore.similarity_search_with_score(query, k=k)

        # 过滤低质量结果
        filtered = [
            (doc.page_content, doc.metadata, score)
            for doc, score in results
            if score >= threshold
        ]

        # 计算检索质量
        quality = SearchQuality(
            total_candidates=len(results),
            qualified_count=len(filtered),
            avg_score=sum(r[2] for r in filtered) / len(filtered) if filtered else 0,
            confidence=self._calculate_confidence(filtered)
        )

        return filtered, quality

    def _calculate_confidence(self, results: list) -> str:
        """计算置信度等级"""
        if not results:
            return "low"
        avg_score = sum(r[2] for r in results) / len(results)
        if avg_score >= 0.85 and len(results) >= 2:
            return "high"
        elif avg_score >= 0.7:
            return "medium"
        return "low"

1.2 拒答与降级策略
Python

# 新增 backend/app/services/ai_response_strategy.py

from enum import Enum
from dataclasses import dataclass

class ResponseStrategy(Enum):
FULL_RAG = "full_rag" # 正常 RAG 回答
PARTIAL_RAG = "partial_rag" # 部分依赖 RAG
GENERAL_LEGAL = "general_legal" # 通用法律知识回答
REFUSE_ANSWER = "refuse" # 拒绝回答
REDIRECT = "redirect" # 建议咨询律师

@dataclass
class StrategyDecision:
strategy: ResponseStrategy
reason: str
confidence: str
disclaimer: str | None = None

class ResponseStrategyDecider:
"""决定回答策略"""

    # 敏感/高风险问题关键词
    HIGH_RISK_KEYWORDS = [
        "刑事", "犯罪", "判刑", "坐牢", "死刑",
        "诉讼时效已过", "伪造", "诈骗"
    ]

    # 需要转介的复杂问题
    COMPLEX_PATTERNS = [
        r"涉及.*金额.*万",
        r"多方.*纠纷",
        r"跨.*境"
    ]

    def decide(
        self,
        query: str,
        search_quality: SearchQuality,
        user_context: dict | None = None
    ) -> StrategyDecision:
        # 检查高风险问题
        if self._is_high_risk(query):
            return StrategyDecision(
                strategy=ResponseStrategy.REDIRECT,
                reason="涉及刑事或高风险法律问题",
                confidence="N/A",
                disclaimer="此类问题建议咨询专业律师，AI仅供参考"
            )

        # 检查复杂问题
        if self._is_complex(query):
            return StrategyDecision(
                strategy=ResponseStrategy.PARTIAL_RAG,
                reason="问题较为复杂",
                confidence=search_quality.confidence,
                disclaimer="问题涉及多个法律领域，建议咨询专业律师获取完整意见"
            )

        # 根据检索质量决策
        if search_quality.confidence == "high":
            return StrategyDecision(
                strategy=ResponseStrategy.FULL_RAG,
                reason="找到高相关法律依据",
                confidence="high"
            )
        elif search_quality.confidence == "medium":
            return StrategyDecision(
                strategy=ResponseStrategy.PARTIAL_RAG,
                reason="找到部分相关法律依据",
                confidence="medium",
                disclaimer="以下回答基于有限的法律参考，建议进一步核实"
            )
        elif search_quality.qualified_count == 0:
            return StrategyDecision(
                strategy=ResponseStrategy.GENERAL_LEGAL,
                reason="未找到直接相关法条",
                confidence="low",
                disclaimer="未找到直接相关法律条文，以下为一般性法律建议"
            )

        return StrategyDecision(
            strategy=ResponseStrategy.PARTIAL_RAG,
            reason="默认策略",
            confidence="medium"
        )

1.3 法条引用结构化与验证
Python

# backend/app/schemas/ai.py 增强

from pydantic import BaseModel, field_validator
from typing import Literal

class LawReference(BaseModel):
"""结构化法条引用"""
law_name: str # 法律名称
article_number: str | None # 条款编号
content: str # 条款内容
relevance_score: float # 相关性分数
source: Literal["rag", "model"] # 来源：检索 or 模型生成
verified: bool = False # 是否已验证

    @field_validator('relevance_score')
    @classmethod
    def validate_score(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('相关性分数必须在0-1之间')
        return v

class EnhancedChatResponse(BaseModel):
session_id: str
answer: str
references: list[LawReference]
strategy_used: str # 使用的回答策略
confidence: str # 置信度
disclaimer: str | None # 免责声明
assistant_message_id: int
created_at: datetime

    # 新增元数据
    metadata: dict = {}              # 可扩展元数据

1.4 多路召回策略
Python

# backend/app/services/retrieval.py

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

class BaseRetriever(ABC):
@abstractmethod
def retrieve(self, query: str, k: int) -> list[RetrievalResult]:
pass

class VectorRetriever(BaseRetriever):
"""向量相似度检索"""
def retrieve(self, query: str, k: int) -> list[RetrievalResult]: # 现有的 Chroma 检索逻辑
pass

class KeywordRetriever(BaseRetriever):
"""关键词检索（BM25）"""
def retrieve(self, query: str, k: int) -> list[RetrievalResult]: # 使用 Elasticsearch 或 内存 BM25
pass

class GraphRetriever(BaseRetriever):
"""知识图谱检索"""
def retrieve(self, query: str, k: int) -> list[RetrievalResult]: # 基于法律实体关系图谱检索
pass

class HybridRetriever:
"""混合检索器"""

    def __init__(self):
        self.retrievers = {
            "vector": VectorRetriever(),
            "keyword": KeywordRetriever(),
            # "graph": GraphRetriever(),  # 可选
        }
        self.weights = {
            "vector": 0.6,
            "keyword": 0.4,
        }

    def retrieve(self, query: str, k: int = 5) -> list[RetrievalResult]:
        """并行多路召回 + 融合排序"""
        all_results = {}

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                name: executor.submit(retriever.retrieve, query, k * 2)
                for name, retriever in self.retrievers.items()
            }

            for name, future in futures.items():
                results = future.result()
                for r in results:
                    key = (r.law_name, r.article_number)
                    if key not in all_results:
                        all_results[key] = {"result": r, "scores": {}}
                    all_results[key]["scores"][name] = r.score

        # RRF (Reciprocal Rank Fusion) 融合
        return self._rrf_fusion(all_results, k)

    def _rrf_fusion(self, results: dict, k: int) -> list[RetrievalResult]:
        """RRF 排序融合"""
        rrf_k = 60  # RRF 常量
        scored = []

        for key, data in results.items():
            rrf_score = sum(
                self.weights.get(source, 0) / (rrf_k + rank)
                for source, rank in self._get_ranks(data["scores"]).items()
            )
            scored.append((data["result"], rrf_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:k]]

二、对话能力增强（优先级：🔴 高）
2.1 意图识别与分类
Python

# backend/app/services/intent_classifier.py

from enum import Enum
from pydantic import BaseModel

class LegalIntent(Enum): # 咨询类
LEGAL_CONSULTATION = "legal_consultation" # 法律咨询
CASE_ANALYSIS = "case_analysis" # 案例分析
DOCUMENT_REVIEW = "document_review" # 文书审查

    # 查询类
    LAW_QUERY = "law_query"                        # 法条查询
    PROCEDURE_QUERY = "procedure_query"            # 流程查询
    FEE_QUERY = "fee_query"                        # 费用查询

    # 服务类
    LAWYER_RECOMMENDATION = "lawyer_recommendation" # 律师推荐
    APPOINTMENT = "appointment"                     # 预约咨询

    # 其他
    GREETING = "greeting"                          # 问候
    OFF_TOPIC = "off_topic"                        # 非法律问题
    UNCLEAR = "unclear"                            # 意图不明确

class IntentResult(BaseModel):
primary_intent: LegalIntent
confidence: float
sub_intents: list[LegalIntent] = []
legal_domain: str | None = None # 法律领域：民事/刑事/行政/劳动等
entities: dict = {} # 识别出的实体

class IntentClassifier:
"""意图识别器"""

    # 意图关键词映射
    INTENT_PATTERNS = {
        LegalIntent.LAW_QUERY: [
            r".*法.*第.*条.*",
            r"法律规定",
            r"法条",
        ],
        LegalIntent.PROCEDURE_QUERY: [
            r"怎么.*起诉",
            r"流程",
            r"需要.*材料",
            r"去哪里.*办",
        ],
        LegalIntent.LAWYER_RECOMMENDATION: [
            r"推荐.*律师",
            r"找.*律师",
            r"律师.*联系",
        ],
        # ... 更多模式
    }

    # 法律领域关键词
    DOMAIN_KEYWORDS = {
        "民事": ["合同", "借款", "债务", "房产", "婚姻", "继承", "侵权"],
        "刑事": ["犯罪", "诈骗", "盗窃", "伤害", "报案"],
        "劳动": ["工资", "社保", "辞退", "加班", "工伤", "劳动合同"],
        "行政": ["行政处罚", "行政复议", "拆迁", "征收"],
        "知识产权": ["专利", "商标", "著作权", "版权"],
    }

    async def classify(self, query: str, context: list[dict] = None) -> IntentResult:
        """
        意图识别
        可以使用规则 + LLM 混合方式
        """
        # 1. 规则匹配（快速）
        rule_result = self._rule_based_classify(query)
        if rule_result.confidence > 0.9:
            return rule_result

        # 2. LLM 辅助（准确）
        llm_result = await self._llm_classify(query, context)

        # 3. 融合结果
        return self._merge_results(rule_result, llm_result)

    def _rule_based_classify(self, query: str) -> IntentResult:
        """规则分类"""
        # 实现规则匹配逻辑
        pass

    async def _llm_classify(self, query: str, context: list) -> IntentResult:
        """LLM 分类"""
        classification_prompt = """
        分析以下法律咨询问题的意图和领域。

        问题：{query}

        请返回JSON格式：
        {{
            "intent": "意图类型",
            "confidence": 0.0-1.0,
            "domain": "法律领域",
            "entities": {{
                "金额": "如有",
                "时间": "如有",
                "主体": ["涉及的人/组织"]
            }}
        }}
        """
        # 调用 LLM
        pass

2.2 对话引导与追问
Python

# backend/app/services/dialogue_manager.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class DialogueState:
"""对话状态"""
session_id: str
intent: LegalIntent
collected_info: dict # 已收集的信息
missing_info: list[str] # 缺失的必要信息
clarification_count: int = 0 # 追问次数
max_clarifications: int = 3 # 最大追问次数

class DialogueManager:
"""对话管理器 - 负责追问和引导"""

    # 不同意图需要的必要信息
    REQUIRED_INFO = {
        LegalIntent.LEGAL_CONSULTATION: [
            "问题描述",
            "相关主体",
            "时间节点",
        ],
        LegalIntent.CASE_ANALYSIS: [
            "案件事实",
            "涉及金额",
            "证据情况",
            "诉求目标",
        ],
        LegalIntent.DOCUMENT_REVIEW: [
            "文书类型",
            "审查目的",
        ],
    }

    # 追问模板
    CLARIFICATION_TEMPLATES = {
        "问题描述": "能否更详细地描述一下您遇到的具体情况？",
        "相关主体": "这个问题涉及哪些人或单位？您与对方是什么关系？",
        "时间节点": "这件事是什么时候发生的？目前进展到什么阶段？",
        "涉及金额": "涉及的金额大概是多少？",
        "证据情况": "您目前有哪些证据材料？比如合同、转账记录、聊天记录等。",
        "诉求目标": "您希望达成什么样的结果？",
    }

    def __init__(self):
        self.states: dict[str, DialogueState] = {}

    def should_clarify(self, session_id: str, intent: LegalIntent, query: str) -> Optional[str]:
        """判断是否需要追问"""
        state = self._get_or_create_state(session_id, intent)

        # 已达最大追问次数
        if state.clarification_count >= state.max_clarifications:
            return None

        # 分析当前消息，更新收集到的信息
        self._extract_and_update_info(state, query)

        # 检查缺失信息
        required = self.REQUIRED_INFO.get(intent, [])
        state.missing_info = [
            info for info in required
            if info not in state.collected_info
        ]

        if state.missing_info:
            state.clarification_count += 1
            # 选择最重要的缺失信息进行追问
            priority_missing = state.missing_info[0]
            return self.CLARIFICATION_TEMPLATES.get(
                priority_missing,
                f"能否补充一下{priority_missing}的信息？"
            )

        return None

    def get_context_summary(self, session_id: str) -> str:
        """获取对话上下文摘要，用于提示词"""
        state = self.states.get(session_id)
        if not state or not state.collected_info:
            return ""

        summary_parts = []
        for key, value in state.collected_info.items():
            summary_parts.append(f"- {key}：{value}")

        return "用户已提供的信息：\n" + "\n".join(summary_parts)

2.3 动态提示词优化
Python

# backend/app/services/prompt_builder.py

class DynamicPromptBuilder:
"""动态提示词构建器"""

    BASE_SYSTEM_PROMPT = """你是一位专业的法律咨询助手，具备中国法律专业知识。

## 角色定位

- 你是法律知识普及者，不是执业律师
- 提供法律参考和建议，不构成正式法律意见
- 对于复杂或高风险问题，建议用户咨询专业律师

## 回答原则

1. 准确性：引用法条时必须准确，不确定时明确说明
2. 完整性：分析问题的多个方面，考虑不同情况
3. 实用性：给出可操作的建议和步骤
4. 谨慎性：涉及风险时充分提示

## 回答结构

1.  问题理解：简要复述用户问题的核心
2.  法律分析：引用相关法条，分析适用情况
3.  风险提示：指出潜在的法律风险
4.  行动建议：给出具体可行的建议
5.  补充说明：如有遗漏，提出追问
    """

        def build(
            self,
            intent: LegalIntent,
            domain: str | None,
            context_summary: str,
            references: list[LawReference],
            strategy: ResponseStrategy,
            disclaimer: str | None
        ) -> str:
            """构建动态提示词"""
            parts = [self.BASE_SYSTEM_PROMPT]

            # 添加领域特定指引
            if domain:
                parts.append(self._get_domain_guidance(domain))

            # 添加意图特定指引
            parts.append(self._get_intent_guidance(intent))

            # 添加上下文摘要
            if context_summary:
                parts.append(f"\n## 用户背景信息\n{context_summary}")

            # 添加检索到的法条参考
            if references:
                ref_text = self._format_references(references)
                parts.append(f"\n## 相关法律参考\n{ref_text}")

            # 添加策略指引
            parts.append(self._get_strategy_guidance(strategy))

            # 添加免责声明要求
            if disclaimer:
                parts.append(f"\n## 特别提醒\n回答末尾请包含：{disclaimer}")

            return "\n".join(parts)

        def _get_domain_guidance(self, domain: str) -> str:
            """领域特定指引"""
            domain_guides = {
                "民事": """

## 民事案件注意事项

- 注意诉讼时效（一般 3 年）
- 关注证据保全
- 考虑调解可能性
  """,
  "刑事": """

## 刑事案件注意事项

- 强调法律后果的严重性
- 建议及时寻求律师帮助
- 提醒当事人的权利（如沉默权）
  """,
  "劳动": """

## 劳动争议注意事项

- 提醒仲裁前置程序
- 注意仲裁时效（1 年）
- 关注证据收集（劳动合同、工资条等）
  """,
  }
  return domain_guides.get(domain, "")
  三、安全与合规（优先级：🔴 高）
  3.1 内容安全过滤
  Python

# backend/app/services/content_safety.py

from enum import Enum
from dataclasses import dataclass
import re

class RiskLevel(Enum):
SAFE = "safe"
LOW = "low"
MEDIUM = "medium"
HIGH = "high"
BLOCKED = "blocked"

@dataclass
class SafetyCheckResult:
risk_level: RiskLevel
triggered_rules: list[str]
suggestion: str | None = None
should_log: bool = False

class ContentSafetyFilter:
"""内容安全过滤器"""

    # 绝对禁止的内容模式
    BLOCKED_PATTERNS = [
        r"如何.*杀人",
        r"怎么.*报复",
        r"教.*制造.*武器",
        r"如何.*洗钱",
    ]

    # 高风险关键词
    HIGH_RISK_KEYWORDS = [
        "自杀", "自残", "极端", "报复社会",
    ]

    # 需要警告的敏感话题
    SENSITIVE_TOPICS = {
        "政治敏感": [r"国家.*领导", r"政府.*腐败"],
        "人身安全": [r"威胁", r"恐吓"],
        "隐私侵犯": [r"人肉搜索", r"曝光.*个人信息"],
    }

    def check_input(self, text: str) -> SafetyCheckResult:
        """检查用户输入"""
        triggered = []

        # 检查绝对禁止
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return SafetyCheckResult(
                    risk_level=RiskLevel.BLOCKED,
                    triggered_rules=[f"blocked:{pattern}"],
                    suggestion="很抱歉，我无法回答这类问题。如需帮助，请联系专业机构。",
                    should_log=True
                )

        # 检查高风险
        for keyword in self.HIGH_RISK_KEYWORDS:
            if keyword in text:
                triggered.append(f"high_risk:{keyword}")

        if triggered:
            return SafetyCheckResult(
                risk_level=RiskLevel.HIGH,
                triggered_rules=triggered,
                suggestion="您的问题涉及敏感内容，我会谨慎回答。如遇紧急情况请拨打110或相关求助热线。",
                should_log=True
            )

        # 检查敏感话题
        for topic, patterns in self.SENSITIVE_TOPICS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    triggered.append(f"sensitive:{topic}")

        if triggered:
            return SafetyCheckResult(
                risk_level=RiskLevel.MEDIUM,
                triggered_rules=triggered,
                should_log=True
            )

        return SafetyCheckResult(
            risk_level=RiskLevel.SAFE,
            triggered_rules=[]
        )

    def check_output(self, text: str) -> SafetyCheckResult:
        """检查AI输出"""
        # 类似的检查逻辑，但规则可能不同
        pass

    def sanitize_output(self, text: str) -> str:
        """清理输出中的敏感信息"""
        # 移除可能泄露的个人信息格式
        text = re.sub(r'\b\d{11}\b', '[电话号码已隐藏]', text)
        text = re.sub(r'\b\d{18}\b', '[身份证号已隐藏]', text)
        return text

3.2 法律免责声明系统
Python

# backend/app/services/disclaimer.py

class DisclaimerManager:
"""免责声明管理"""

    GENERAL_DISCLAIMER = """

---

📌 **重要提示**：以上内容仅供参考，不构成正式法律意见。具体法律问题请咨询专业律师。
"""

    DOMAIN_DISCLAIMERS = {
        "刑事": """

---

⚠️ **特别提醒**：刑事案件关系重大，强烈建议您尽快委托专业刑事辩护律师。如遇紧急情况，请立即拨打 110。
""",
"婚姻家事": """

---

💡 **温馨提示**：婚姻家事纠纷涉及情感和法律的复杂交织，建议在做重大决定前咨询专业律师，充分了解法律后果。
""",
}

    RISK_DISCLAIMERS = {
        RiskLevel.HIGH: """

---

🔴 **高风险提示**：您咨询的问题涉及较高法律风险，AI 回答仅供初步了解。请务必咨询专业律师获取针对性意见。
""",
RiskLevel.MEDIUM: """

---

🟡 **风险提示**：此类问题情况复杂，建议结合实际情况咨询专业律师。
""",
}

    def get_disclaimer(
        self,
        domain: str | None,
        risk_level: RiskLevel,
        strategy: ResponseStrategy
    ) -> str:
        """获取适合的免责声明"""
        disclaimers = []

        # 风险等级声明（优先）
        if risk_level in self.RISK_DISCLAIMERS:
            disclaimers.append(self.RISK_DISCLAIMERS[risk_level])

        # 领域特定声明
        if domain in self.DOMAIN_DISCLAIMERS:
            disclaimers.append(self.DOMAIN_DISCLAIMERS[domain])

        # 策略相关声明
        if strategy == ResponseStrategy.REDIRECT:
            disclaimers.append("\n建议您通过平台预约专业律师咨询。")

        # 默认通用声明
        if not disclaimers:
            disclaimers.append(self.GENERAL_DISCLAIMER)

        return "\n".join(disclaimers)

3.3 审计日志
Python

# backend/app/services/audit_logger.py

from datetime import datetime
from enum import Enum
import json

class AuditEventType(Enum):
AI_QUERY = "ai_query"
AI_RESPONSE = "ai_response"
SAFETY_TRIGGER = "safety_trigger"
RATE_LIMIT_HIT = "rate_limit_hit"
EXPORT_REQUEST = "export_request"

class AIAuditLogger:
"""AI 咨询审计日志"""

    def __init__(self, db_session):
        self.db = db_session

    async def log(
        self,
        event_type: AuditEventType,
        session_id: str,
        user_id: int | None,
        data: dict,
        metadata: dict | None = None
    ):
        """记录审计日志"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "session_id": session_id,
            "user_id": user_id,
            "data": self._sanitize_data(data),
            "metadata": metadata or {},
        }

        # 写入数据库或日志系统
        await self._persist(log_entry)

    def _sanitize_data(self, data: dict) -> dict:
        """脱敏处理"""
        sanitized = data.copy()

        # 对用户消息进行脱敏（如有需要）
        if "message" in sanitized and len(sanitized["message"]) > 500:
            sanitized["message"] = sanitized["message"][:500] + "...[truncated]"

        return sanitized

    async def _persist(self, log_entry: dict):
        """持久化日志"""
        # 可以写入数据库表 ai_audit_logs
        # 或发送到 ELK/Loki 等日志系统
        pass

四、可观测性增强（优先级：🟡 中）
4.1 链路追踪
Python

# backend/app/middleware/tracing.py

import uuid
from contextvars import ContextVar
from fastapi import Request

# 请求上下文

request_id_var: ContextVar[str] = ContextVar('request_id', default='')
trace_context: ContextVar[dict] = ContextVar('trace_context', default={})

async def tracing_middleware(request: Request, call_next):
"""链路追踪中间件"""
request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
request_id_var.set(request_id)

    trace_ctx = {
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
        "start_time": time.time(),
        "spans": []
    }
    trace_context.set(trace_ctx)

    response = await call_next(request)

    # 添加响应头
    response.headers["X-Request-ID"] = request_id

    # 记录完整链路
    trace_ctx["end_time"] = time.time()
    trace_ctx["duration_ms"] = (trace_ctx["end_time"] - trace_ctx["start_time"]) * 1000

    # 发送到追踪系统
    await send_trace(trace_ctx)

    return response

def trace_span(name: str):
"""装饰器：记录函数执行时间"""
def decorator(func):
@functools.wraps(func)
async def wrapper(\*args, \*\*kwargs):
ctx = trace_context.get()
span = {
"name": name,
"start_time": time.time(),
}

            try:
                result = await func(*args, **kwargs)
                span["status"] = "success"
                return result
            except Exception as e:
                span["status"] = "error"
                span["error"] = str(e)
                raise
            finally:
                span["end_time"] = time.time()
                span["duration_ms"] = (span["end_time"] - span["start_time"]) * 1000
                ctx["spans"].append(span)

        return wrapper
    return decorator

4.2 性能指标收集
Python

# backend/app/services/metrics.py

from prometheus_client import Counter, Histogram, Gauge
import time

# 定义指标

AI_REQUEST_COUNTER = Counter(
'ai_consultation_requests_total',
'Total AI consultation requests',
['endpoint', 'status', 'user_type']
)

AI_RESPONSE_LATENCY = Histogram(
'ai_response_latency_seconds',
'AI response latency',
['endpoint', 'strategy'],
buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

RAG_RETRIEVAL_LATENCY = Histogram(
'rag_retrieval_latency_seconds',
'RAG retrieval latency',
buckets=[0.1, 0.25, 0.5, 1.0, 2.0]
)

LLM_TOKEN_USAGE = Counter(
'llm_token_usage_total',
'Total LLM token usage',
['model', 'type'] # type: prompt/completion
)

ACTIVE_SESSIONS = Gauge(
'ai_active_sessions',
'Number of active AI consultation sessions'
)

class MetricsCollector:
"""指标收集器"""

    def record_request(
        self,
        endpoint: str,
        status: str,
        user_type: str,  # "user" or "guest"
        latency: float,
        strategy: str = "unknown"
    ):
        AI_REQUEST_COUNTER.labels(
            endpoint=endpoint,
            status=status,
            user_type=user_type
        ).inc()

        AI_RESPONSE_LATENCY.labels(
            endpoint=endpoint,
            strategy=strategy
        ).observe(latency)

    def record_retrieval(self, latency: float):
        RAG_RETRIEVAL_LATENCY.observe(latency)

    def record_token_usage(self, model: str, prompt_tokens: int, completion_tokens: int):
        LLM_TOKEN_USAGE.labels(model=model, type="prompt").inc(prompt_tokens)
        LLM_TOKEN_USAGE.labels(model=model, type="completion").inc(completion_tokens)

4.3 质量评估仪表板数据
Python

# backend/app/services/quality_analytics.py

from datetime import datetime, timedelta
from sqlalchemy import func

class AIQualityAnalytics:
"""AI 质量分析服务"""

    def __init__(self, db):
        self.db = db

    async def get_dashboard_data(self, days: int = 7) -> dict:
        """获取仪表板数据"""
        start_date = datetime.utcnow() - timedelta(days=days)

        return {
            "overview": await self._get_overview(start_date),
            "rating_distribution": await self._get_rating_distribution(start_date),
            "daily_trend": await self._get_daily_trend(start_date),
            "top_topics": await self._get_top_topics(start_date),
            "response_quality": await self._get_response_quality_metrics(start_date),
        }

    async def _get_overview(self, start_date) -> dict:
        """概览数据"""
        total_sessions = await self.db.execute(
            select(func.count(Consultation.id))
            .where(Consultation.created_at >= start_date)
        )

        total_messages = await self.db.execute(
            select(func.count(ChatMessage.id))
            .where(ChatMessage.created_at >= start_date)
        )

        rated_messages = await self.db.execute(
            select(func.count(ChatMessage.id))
            .where(
                ChatMessage.created_at >= start_date,
                ChatMessage.rating.isnot(None)
            )
        )

        avg_rating = await self.db.execute(
            select(func.avg(ChatMessage.rating))
            .where(
                ChatMessage.created_at >= start_date,
                ChatMessage.rating.isnot(None)
            )
        )

        return {
            "total_sessions": total_sessions.scalar(),
            "total_messages": total_messages.scalar(),
            "rated_count": rated_messages.scalar(),
            "average_rating": round(avg_rating.scalar() or 0, 2),
        }

    async def _get_rating_distribution(self, start_date) -> dict:
        """评分分布"""
        result = await self.db.execute(
            select(ChatMessage.rating, func.count(ChatMessage.id))
            .where(
                ChatMessage.created_at >= start_date,
                ChatMessage.rating.isnot(None)
            )
            .group_by(ChatMessage.rating)
        )

        distribution = {1: 0, 2: 0, 3: 0}
        for rating, count in result:
            distribution[rating] = count

        return distribution

五、用户体验优化（优先级：🟡 中）
5.1 智能问题建议
Python

# backend/app/services/question_suggestion.py

class QuestionSuggestionService:
"""智能问题建议服务"""

    # 热门问题分类
    POPULAR_QUESTIONS = {
        "劳动纠纷": [
            "公司拖欠工资怎么办？",
            "被公司辞退有什么补偿？",
            "加班不给加班费合法吗？",
        ],
        "合同纠纷": [
            "对方违约怎么索赔？",
            "合同没签字有效吗？",
            "定金和订金有什么区别？",
        ],
        "婚姻家庭": [
            "离婚财产怎么分割？",
            "孩子抚养权归谁？",
            "离婚需要什么条件？",
        ],
    }

    async def get_initial_suggestions(self, user_id: int | None = None) -> list[str]:
        """获取初始问题建议"""
        if user_id:
            # 基于用户历史推荐
            history_based = await self._get_history_based_suggestions(user_id)
            if history_based:
                return history_based[:3]

        # 返回热门问题
        return self._get_trending_questions()[:6]

    async def get_followup_suggestions(
        self,
        session_id: str,
        last_answer: str,
        intent: LegalIntent
    ) -> list[str]:
        """获取追问建议"""
        # 基于对话内容和意图生成追问
        followups = []

        if intent == LegalIntent.LEGAL_CONSULTATION:
            followups = [
                "这种情况的诉讼时效是多久？",
                "我需要准备什么证据？",
                "走法律程序大概需要多长时间？",
                "有什么风险需要注意？",
            ]

        return followups[:4]

    def _get_trending_questions(self) -> list[str]:
        """获取热门问题"""
        import random
        all_questions = []
        for questions in self.POPULAR_QUESTIONS.values():
            all_questions.extend(questions)
        random.shuffle(all_questions)
        return all_questions

5.2 相似案例推荐
Python

# backend/app/services/case_recommendation.py

class CaseRecommendationService:
"""相似案例推荐服务"""

    def __init__(self, knowledge_base: LegalKnowledgeBase):
        self.kb = knowledge_base

    async def recommend_cases(
        self,
        query: str,
        context: str,
        limit: int = 3
    ) -> list[CaseRecommendation]:
        """推荐相似案例"""
        # 合并查询和上下文
        search_text = f"{query}\n{context}"

        # 从案例库检索（假设有独立的案例向量库）
        results = await self.case_vectorstore.similarity_search(
            search_text,
            k=limit,
            filter={"type": "case"}
        )

        return [
            CaseRecommendation(
                case_id=r.metadata.get("case_id"),
                title=r.metadata.get("title"),
                summary=r.page_content[:200],
                relevance_score=r.score,
                court=r.metadata.get("court"),
                date=r.metadata.get("date"),
            )
            for r in results
        ]

5.3 前端体验优化建议
TypeScript

// frontend/src/components/chat/EnhancedChatInput.tsx

interface ChatInputProps {
onSend: (message: string) => void;
suggestions: string[];
isLoading: boolean;
}

const EnhancedChatInput: React.FC<ChatInputProps> = ({
onSend,
suggestions,
isLoading,
}) => {
const [input, setInput] = useState('');
const [showSuggestions, setShowSuggestions] = useState(true);

return (

<div className="chat-input-container">
{/_ 问题建议 _/}
{showSuggestions && suggestions.length > 0 && (
<div className="suggestions-panel">
<p className="text-sm text-gray-500 mb-2">您可能想问：</p>
<div className="flex flex-wrap gap-2">
{suggestions.map((s, i) => (
<button
key={i}
onClick={() => {
setInput(s);
setShowSuggestions(false);
}}
className="suggestion-chip" >
{s}
</button>
))}
</div>
</div>
)}

      {/* 输入框 */}
      <div className="input-wrapper">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="请描述您的法律问题..."
          className="flex-1"
          rows={3}
        />
        <button
          onClick={() => {
            onSend(input);
            setInput('');
          }}
          disabled={!input.trim() || isLoading}
          className="send-button"
        >
          {isLoading ? <Spinner /> : <SendIcon />}
        </button>
      </div>

      {/* 输入提示 */}
      <p className="input-hint text-xs text-gray-400">
        💡 提示：描述越详细，回答越准确。包含时间、金额、相关人员等信息会更好。
      </p>
    </div>

);
};
六、业务功能扩展（优先级：🟢 低-中）
6.1 律师转接功能
Python

# backend/app/routers/ai.py 新增端点

@router.post("/consultations/{session_id}/transfer-to-lawyer")
async def transfer_to_lawyer(
session_id: str,
transfer_request: LawyerTransferRequest,
current_user: User = Depends(get_current_user),
db: Session = Depends(get_db)
):
"""
将 AI 咨询转接给真人律师 1. 生成咨询摘要 2. 创建律师预约单 3. 推荐匹配律师
""" # 验证会话归属
consultation = await get_consultation_or_404(db, session_id, current_user)

    # 生成咨询摘要
    summary = await ai_assistant.generate_consultation_summary(session_id)

    # 匹配律师
    matched_lawyers = await lawyer_matching_service.match(
        domain=summary.detected_domain,
        location=transfer_request.location,
        urgency=transfer_request.urgency,
        budget=transfer_request.budget
    )

    # 创建预约
    appointment = await appointment_service.create(
        user_id=current_user.id,
        consultation_id=consultation.id,
        summary=summary,
        preferred_lawyers=matched_lawyers[:5],
        preferred_time=transfer_request.preferred_time,
    )

    return {
        "appointment_id": appointment.id,
        "summary": summary,
        "recommended_lawyers": matched_lawyers[:5],
        "estimated_cost": calculate_estimated_cost(matched_lawyers),
    }

6.2 法律文书辅助生成
Python

# backend/app/services/document_generator.py

class LegalDocumentGenerator:
"""法律文书生成器"""

    DOCUMENT_TEMPLATES = {
        "起诉状": {
            "fields": ["原告信息", "被告信息", "诉讼请求", "事实与理由", "证据清单"],
            "template_path": "templates/lawsuit_complaint.jinja2",
        },
        "劳动仲裁申请书": {
            "fields": ["申请人信息", "被申请人信息", "仲裁请求", "事实与理由"],
            "template_path": "templates/labor_arbitration.jinja2",
        },
        "离婚协议书": {
            "fields": ["双方信息", "财产分割", "子女抚养", "债务处理"],
            "template_path": "templates/divorce_agreement.jinja2",
        },
    }

    async def generate(
        self,
        document_type: str,
        consultation_session_id: str,
        user_provided_data: dict,
        db: Session
    ) -> DocumentGenerationResult:
        """
        基于咨询内容生成法律文书
        """
        # 获取咨询历史
        consultation = await self._get_consultation(db, consultation_session_id)

        # 从对话中提取结构化信息
        extracted_info = await self._extract_document_info(
            consultation.messages,
            self.DOCUMENT_TEMPLATES[document_type]["fields"]
        )

        # 合并用户提供的数据
        merged_data = {**extracted_info, **user_provided_data}

        # 检查必填字段
        missing_fields = self._check_required_fields(document_type, merged_data)
        if missing_fields:
            return DocumentGenerationResult(
                status="incomplete",
                missing_fields=missing_fields,
                questions=self._generate_questions(missing_fields),
            )

        # 生成文书
        document = await self._render_document(document_type, merged_data)

        return DocumentGenerationResult(
            status="success",
            document=document,
            format="docx",
            disclaimer="此文书由AI辅助生成，仅供参考。正式使用前请咨询专业律师审核。",
        )

6.3 风险评估报告
Python

# backend/app/services/risk_assessment.py

@dataclass
class RiskAssessmentReport:
session_id: str
generated_at: datetime
case_summary: str
risk_items: list[RiskItem]
overall_risk_level: str # low/medium/high
recommendations: list[str]
next_steps: list[str]
estimated_timeline: str | None
estimated_cost_range: tuple[int, int] | None

@dataclass
class RiskItem:
category: str # 法律风险/时效风险/证据风险/经济风险
description: str
severity: str # low/medium/high
mitigation: str # 应对措施

class RiskAssessmentService:
"""风险评估服务"""

    async def generate_report(
        self,
        session_id: str,
        db: Session
    ) -> RiskAssessmentReport:
        """生成风险评估报告"""
        # 获取咨询记录
        consultation = await self._get_consultation(db, session_id)

        # 使用LLM分析风险
        risk_analysis = await self._analyze_risks(consultation.messages)

        # 结构化风险项
        risk_items = self._structure_risk_items(risk_analysis)

        # 计算整体风险等级
        overall_level = self._calculate_overall_risk(risk_items)

        # 生成建议
        recommendations = await self._generate_recommendations(
            risk_items,
            overall_level
        )

        return RiskAssessmentReport(
            session_id=session_id,
            generated_at=datetime.utcnow(),
            case_summary=risk_analysis.summary,
            risk_items=risk_items,
            overall_risk_level=overall_level,
            recommendations=recommendations,
            next_steps=self._get_next_steps(overall_level),
            estimated_timeline=risk_analysis.timeline,
            estimated_cost_range=risk_analysis.cost_range,
        )

七、实施路线图建议
第一阶段（1-2 周）- 核心质量提升
任务 优先级 预估工时
RAG 质量控制与阈值 🔴 高 2 天
拒答与降级策略 🔴 高 1 天
内容安全过滤 🔴 高 2 天
法律免责声明系统 🔴 高 1 天
审计日志基础版 🔴 高 1 天
第二阶段（2-3 周）- 对话能力增强
任务 优先级 预估工时
意图识别与分类 🔴 高 3 天
对话引导与追问 🔴 高 2 天
动态提示词优化 🟡 中 2 天
智能问题建议 🟡 中 1 天
第三阶段（2 周）- 可观测性
任务 优先级 预估工时
链路追踪 🟡 中 2 天
性能指标收集 🟡 中 1 天
质量仪表板 🟡 中 2 天
第四阶段（2-3 周）- 业务扩展
任务 优先级 预估工时
律师转接功能 🟢 中 3 天
法律文书辅助 🟢 低 5 天
风险评估报告 🟢 低 3 天
八、技术债务与建议修复
8.1 当前技术债务
Markdown

1. **内存会话缓存** - 多实例部署不一致
   - 建议：迁移到 Redis 或完全依赖 DB
2. **RAG 检索无质量控制** - 可能返回不相关结果
   - 建议：增加阈值过滤
3. **缺少请求追踪** - 排查问题困难
   - 建议：增加 request_id 贯穿全链路
4. **Token 使用无监控** - 成本不可控
   - 建议：增加 token 计数和告警
5. **错误处理不统一** - 前端难以处理
   - 建议：统一错误响应格式
     8.2 统一错误响应建议
     Python

# backend/app/schemas/error.py

class ErrorResponse(BaseModel):
code: str # 业务错误码
message: str # 用户可见消息
detail: str | None # 开发调试信息
request_id: str # 请求追踪 ID
timestamp: datetime
suggestions: list[str] = [] # 建议操作

# 使用示例

class AIErrorCode:
RAG_NO_RESULT = "AI_001"
LLM_TIMEOUT = "AI_002"
CONTENT_BLOCKED = "AI_003"
RATE_LIMITED = "AI_004"
SESSION_NOT_FOUND = "AI_005"

AI 法律咨询模块扩展功能清单
除了之前的建议，以下是更多实用性功能扩展，按前端、后端、全栈联动三个维度分类：

一、前端功能扩展
1.1 输入能力增强
语音输入
TypeScript

// frontend/src/components/chat/VoiceInput.tsx

import { useState, useRef } from 'react';
import { Mic, MicOff, Loader2 } from 'lucide-react';

interface VoiceInputProps {
onTranscript: (text: string) => void;
disabled?: boolean;
}

export const VoiceInput: React.FC<VoiceInputProps> = ({ onTranscript, disabled }) => {
const [isRecording, setIsRecording] = useState(false);
const [isProcessing, setIsProcessing] = useState(false);
const mediaRecorderRef = useRef<MediaRecorder | null>(null);
const chunksRef = useRef<Blob[]>([]);

const startRecording = async () => {
try {
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
const mediaRecorder = new MediaRecorder(stream);
mediaRecorderRef.current = mediaRecorder;
chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        setIsProcessing(true);
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });

        // 发送到后端转文字
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');

        try {
          const response = await fetch('/api/ai/speech-to-text', {
            method: 'POST',
            body: formData,
          });
          const { text } = await response.json();
          onTranscript(text);
        } catch (error) {
          console.error('语音识别失败:', error);
        } finally {
          setIsProcessing(false);
        }

        // 释放麦克风
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('无法访问麦克风:', error);
    }

};

const stopRecording = () => {
if (mediaRecorderRef.current && isRecording) {
mediaRecorderRef.current.stop();
setIsRecording(false);
}
};

return (
<button
onClick={isRecording ? stopRecording : startRecording}
disabled={disabled || isProcessing}
className={`p-2 rounded-full transition-colors ${
        isRecording 
          ? 'bg-red-500 text-white animate-pulse' 
          : 'bg-gray-100 hover:bg-gray-200'
      }`}
title={isRecording ? '点击停止录音' : '点击开始语音输入'} >
{isProcessing ? (
<Loader2 className="w-5 h-5 animate-spin" />
) : isRecording ? (
<MicOff className="w-5 h-5" />
) : (
<Mic className="w-5 h-5" />
)}
</button>
);
};
图片/文件上传（合同、证据等）
TypeScript

// frontend/src/components/chat/FileUpload.tsx

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, X, Image, FileText } from 'lucide-react';

interface UploadedFile {
id: string;
name: string;
type: string;
size: number;
preview?: string;
uploadProgress: number;
status: 'uploading' | 'success' | 'error';
analysisResult?: FileAnalysisResult;
}

interface FileAnalysisResult {
fileType: 'contract' | 'evidence' | 'id_document' | 'other';
extractedText: string;
keyPoints: string[];
suggestedQuestions: string[];
}

export const FileUpload: React.FC<{
onFileAnalyzed: (result: FileAnalysisResult) => void;
maxFiles?: number;
}> = ({ onFileAnalyzed, maxFiles = 5 }) => {
const [files, setFiles] = useState<UploadedFile[]>([]);

const onDrop = useCallback(async (acceptedFiles: File[]) => {
for (const file of acceptedFiles) {
const id = Math.random().toString(36).substr(2, 9);

      // 添加到列表
      const newFile: UploadedFile = {
        id,
        name: file.name,
        type: file.type,
        size: file.size,
        preview: file.type.startsWith('image/')
          ? URL.createObjectURL(file)
          : undefined,
        uploadProgress: 0,
        status: 'uploading',
      };

      setFiles(prev => [...prev, newFile]);

      // 上传并分析
      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/ai/analyze-file', {
          method: 'POST',
          body: formData,
        });

        const result = await response.json();

        setFiles(prev => prev.map(f =>
          f.id === id
            ? { ...f, status: 'success', uploadProgress: 100, analysisResult: result }
            : f
        ));

        onFileAnalyzed(result);
      } catch (error) {
        setFiles(prev => prev.map(f =>
          f.id === id ? { ...f, status: 'error' } : f
        ));
      }
    }

}, [onFileAnalyzed]);

const { getRootProps, getInputProps, isDragActive } = useDropzone({
onDrop,
maxFiles,
accept: {
'image/\*': ['.png', '.jpg', '.jpeg'],
'application/pdf': ['.pdf'],
'application/msword': ['.doc'],
'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
},
});

const removeFile = (id: string) => {
setFiles(prev => prev.filter(f => f.id !== id));
};

return (

<div className="space-y-3">
{/_ 拖拽区域 _/}
<div
{...getRootProps()}
className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
          isDragActive 
            ? 'border-blue-500 bg-blue-50' 
            : 'border-gray-300 hover:border-gray-400'
        }`} >
<input {...getInputProps()} />
<Upload className="w-8 h-8 mx-auto mb-2 text-gray-400" />
<p className="text-sm text-gray-600">
{isDragActive
? '释放文件以上传'
: '拖拽或点击上传合同、证据图片等'}
</p>
<p className="text-xs text-gray-400 mt-1">
支持 PNG、JPG、PDF、Word（最多{maxFiles}个文件）
</p>
</div>

      {/* 文件列表 */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map(file => (
            <div
              key={file.id}
              className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg"
            >
              {file.preview ? (
                <img src={file.preview} className="w-10 h-10 object-cover rounded" />
              ) : (
                <FileText className="w-10 h-10 text-gray-400" />
              )}

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{file.name}</p>
                <p className="text-xs text-gray-500">
                  {file.status === 'uploading' && '正在分析...'}
                  {file.status === 'success' && `识别为: ${file.analysisResult?.fileType}`}
                  {file.status === 'error' && '分析失败'}
                </p>
              </div>

              <button onClick={() => removeFile(file.id)}>
                <X className="w-4 h-4 text-gray-400 hover:text-red-500" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>

);
};
1.2 对话展示增强
法条引用弹窗/高亮
TypeScript

// frontend/src/components/chat/LawReferencePopover.tsx

import { useState } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Scale, ExternalLink, Copy, Check } from 'lucide-react';

interface LawReference {
lawName: string;
articleNumber: string;
content: string;
effectiveDate?: string;
source?: string;
}

export const LawReferenceHighlight: React.FC<{
text: string;
references: LawReference[];
}> = ({ text, references }) => {
// 将法条名称转为正则匹配模式
const patterns = references.map(ref => ({
pattern: new RegExp(`(《${ref.lawName}》第?${ref.articleNumber}条?)`, 'g'),
reference: ref,
}));

// 解析文本，将法条引用转为可点击元素
const parseText = () => {
let result = text;
const elements: React.ReactNode[] = [];
let lastIndex = 0;

    patterns.forEach(({ pattern, reference }) => {
      let match;
      while ((match = pattern.exec(text)) !== null) {
        // 添加匹配前的普通文本
        if (match.index > lastIndex) {
          elements.push(text.slice(lastIndex, match.index));
        }

        // 添加法条引用弹窗
        elements.push(
          <LawReferencePopover
            key={match.index}
            trigger={match[0]}
            reference={reference}
          />
        );

        lastIndex = match.index + match[0].length;
      }
    });

    // 添加剩余文本
    if (lastIndex < text.length) {
      elements.push(text.slice(lastIndex));
    }

    return elements.length > 0 ? elements : text;

};

return <>{parseText()}</>;
};

const LawReferencePopover: React.FC<{
trigger: string;
reference: LawReference;
}> = ({ trigger, reference }) => {
const [copied, setCopied] = useState(false);

const copyContent = () => {
navigator.clipboard.writeText(reference.content);
setCopied(true);
setTimeout(() => setCopied(false), 2000);
};

return (
<Popover>
<PopoverTrigger asChild>
<span className="text-blue-600 bg-blue-50 px-1 rounded cursor-pointer hover:bg-blue-100 transition-colors">
{trigger}
</span>
</PopoverTrigger>
<PopoverContent className="w-96 p-0">

<div className="p-4">
{/_ 标题 _/}
<div className="flex items-center gap-2 mb-3">
<Scale className="w-5 h-5 text-blue-600" />
<h4 className="font-semibold">
《{reference.lawName}》第{reference.articleNumber}条
</h4>
</div>

          {/* 法条内容 */}
          <div className="bg-gray-50 p-3 rounded-lg text-sm leading-relaxed max-h-48 overflow-y-auto">
            {reference.content}
          </div>

          {/* 元信息 */}
          {reference.effectiveDate && (
            <p className="text-xs text-gray-500 mt-2">
              生效日期：{reference.effectiveDate}
            </p>
          )}

          {/* 操作按钮 */}
          <div className="flex gap-2 mt-3">
            <button
              onClick={copyContent}
              className="flex items-center gap-1 text-xs text-gray-600 hover:text-gray-900"
            >
              {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              {copied ? '已复制' : '复制'}
            </button>

            {reference.source && (
              <a
                href={reference.source}
                target="_blank"
                className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
              >
                <ExternalLink className="w-3 h-3" />
                查看原文
              </a>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>

);
};
AI 思考过程展示（透明化）
TypeScript

// frontend/src/components/chat/ThinkingProcess.tsx

import { useState } from 'react';
import { ChevronDown, ChevronUp, Brain, Search, FileText, Lightbulb } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface ThinkingStep {
type: 'intent' | 'retrieval' | 'analysis' | 'generation';
title: string;
content: string;
duration?: number;
metadata?: Record<string, any>;
}

interface ThinkingProcessProps {
steps: ThinkingStep[];
isThinking: boolean;
}

const stepIcons = {
intent: Brain,
retrieval: Search,
analysis: FileText,
generation: Lightbulb,
};

const stepColors = {
intent: 'text-purple-600 bg-purple-50',
retrieval: 'text-blue-600 bg-blue-50',
analysis: 'text-green-600 bg-green-50',
generation: 'text-orange-600 bg-orange-50',
};

export const ThinkingProcess: React.FC<ThinkingProcessProps> = ({
steps,
isThinking,
}) => {
const [isExpanded, setIsExpanded] = useState(false);

if (steps.length === 0 && !isThinking) return null;

return (

<div className="mb-3">
{/_ 折叠标题 _/}
<button
onClick={() => setIsExpanded(!isExpanded)}
className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700" >
<Brain className="w-4 h-4" />
<span>AI 思考过程</span>
{isThinking && (
<span className="flex items-center gap-1">
<span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
思考中...
</span>
)}
{isExpanded ? (
<ChevronUp className="w-4 h-4" />
) : (
<ChevronDown className="w-4 h-4" />
)}
</button>

      {/* 展开内容 */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-2 pl-6 border-l-2 border-gray-200">
              {steps.map((step, index) => {
                const Icon = stepIcons[step.type];
                const colorClass = stepColors[step.type];

                return (
                  <div key={index} className="flex items-start gap-2">
                    <div className={`p-1 rounded ${colorClass}`}>
                      <Icon className="w-3 h-3" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-700">
                        {step.title}
                        {step.duration && (
                          <span className="ml-2 text-xs text-gray-400">
                            {step.duration}ms
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-gray-500">{step.content}</p>

                      {/* 检索结果预览 */}
                      {step.type === 'retrieval' && step.metadata?.results && (
                        <div className="mt-1 text-xs text-gray-400">
                          找到 {step.metadata.results.length} 条相关法条
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* 思考中动画 */}
              {isThinking && (
                <div className="flex items-center gap-2 text-gray-400">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>

);
};
消息操作工具栏
TypeScript

// frontend/src/components/chat/MessageActions.tsx

import { useState } from 'react';
import {
Copy, Share2, Bookmark, BookmarkCheck,
ThumbsUp, ThumbsDown, RotateCcw, MoreHorizontal,
Download, Flag, Volume2
} from 'lucide-react';
import {
DropdownMenu,
DropdownMenuContent,
DropdownMenuItem,
DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';

interface MessageActionsProps {
messageId: number;
content: string;
role: 'user' | 'assistant';
isBookmarked?: boolean;
rating?: number;
onRate: (rating: number) => void;
onBookmark: () => void;
onRegenerate?: () => void;
}

export const MessageActions: React.FC<MessageActionsProps> = ({
messageId,
content,
role,
isBookmarked,
rating,
onRate,
onBookmark,
onRegenerate,
}) => {
const [showActions, setShowActions] = useState(false);

const copyToClipboard = async () => {
await navigator.clipboard.writeText(content);
toast.success('已复制到剪贴板');
};

const shareMessage = async () => {
if (navigator.share) {
await navigator.share({
title: '法律咨询回答',
text: content.slice(0, 200) + '...',
url: window.location.href,
});
} else {
// fallback: 复制链接
await navigator.clipboard.writeText(
`${window.location.origin}/share/message/${messageId}`
);
toast.success('分享链接已复制');
}
};

const speakContent = () => {
const utterance = new SpeechSynthesisUtterance(content);
utterance.lang = 'zh-CN';
utterance.rate = 0.9;
speechSynthesis.speak(utterance);
};

const reportMessage = () => {
// 打开举报弹窗
toast.info('已记录反馈，我们会尽快处理');
};

return (

<div
className="flex items-center gap-1 mt-2"
onMouseEnter={() => setShowActions(true)}
onMouseLeave={() => setShowActions(false)} >
{/_ 快捷操作 _/}
<button onClick={copyToClipboard} className="action-btn" title="复制">
<Copy className="w-4 h-4" />
</button>

      {role === 'assistant' && (
        <>
          {/* 评价按钮 */}
          <button
            onClick={() => onRate(3)}
            className={`action-btn ${rating === 3 ? 'text-green-600' : ''}`}
            title="有帮助"
          >
            <ThumbsUp className="w-4 h-4" />
          </button>
          <button
            onClick={() => onRate(1)}
            className={`action-btn ${rating === 1 ? 'text-red-600' : ''}`}
            title="没帮助"
          >
            <ThumbsDown className="w-4 h-4" />
          </button>

          {/* 收藏 */}
          <button onClick={onBookmark} className="action-btn" title="收藏">
            {isBookmarked ? (
              <BookmarkCheck className="w-4 h-4 text-yellow-500" />
            ) : (
              <Bookmark className="w-4 h-4" />
            )}
          </button>

          {/* 重新生成 */}
          {onRegenerate && (
            <button onClick={onRegenerate} className="action-btn" title="重新生成">
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
        </>
      )}

      {/* 更多操作 */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="action-btn">
            <MoreHorizontal className="w-4 h-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onClick={shareMessage}>
            <Share2 className="w-4 h-4 mr-2" />
            分享
          </DropdownMenuItem>
          <DropdownMenuItem onClick={speakContent}>
            <Volume2 className="w-4 h-4 mr-2" />
            朗读
          </DropdownMenuItem>
          {role === 'assistant' && (
            <DropdownMenuItem onClick={reportMessage}>
              <Flag className="w-4 h-4 mr-2" />
              报告问题
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>

);
};
1.3 实用工具组件
诉讼时效计算器
TypeScript

// frontend/src/components/tools/StatuteOfLimitationsCalculator.tsx

import { useState } from 'react';
import { Calendar, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { format, addYears, addMonths, differenceInDays, isPast } from 'date-fns';

interface LimitationRule {
id: string;
name: string;
category: string;
period: { years?: number; months?: number };
description: string;
legalBasis: string;
notes?: string;
}

const LIMITATION_RULES: LimitationRule[] = [
{
id: 'general',
name: '一般诉讼时效',
category: '民事',
period: { years: 3 },
description: '向人民法院请求保护民事权利的诉讼时效期间',
legalBasis: '《民法典》第一百八十八条',
},
{
id: 'personal_injury',
name: '人身损害赔偿',
category: '侵权',
period: { years: 3 },
description: '身体受到伤害要求赔偿的',
legalBasis: '《民法典》第一百八十八条',
},
{
id: 'labor_dispute',
name: '劳动争议仲裁',
category: '劳动',
period: { years: 1 },
description: '劳动争议申请仲裁的时效期间',
legalBasis: '《劳动争议调解仲裁法》第二十七条',
notes: '特殊情况：拖欠劳动报酬争议，劳动关系存续期间不受限制',
},
{
id: 'contract_quality',
name: '产品质量瑕疵',
category: '合同',
period: { years: 2 },
description: '出卖人交付标的物不符合质量要求的',
legalBasis: '《民法典》第六百二十一条',
},
{
id: 'lease_payment',
name: '租金追索',
category: '合同',
period: { years: 3 },
description: '延付或者拒付租金的',
legalBasis: '《民法典》第一百八十八条',
},
{
id: 'inheritance',
name: '继承权纠纷',
category: '继承',
period: { years: 3 },
description: '继承权纠纷提起诉讼的期限',
legalBasis: '《民法典》第一百八十八条',
notes: '自继承开始之日起超过二十年的，不得再提起诉讼',
},
];

export const StatuteOfLimitationsCalculator: React.FC = () => {
const [selectedRule, setSelectedRule] = useState<LimitationRule | null>(null);
const [startDate, setStartDate] = useState<string>('');
const [result, setResult] = useState<{
deadline: Date;
daysRemaining: number;
isExpired: boolean;
} | null>(null);

const calculate = () => {
if (!selectedRule || !startDate) return;

    const start = new Date(startDate);
    let deadline = start;

    if (selectedRule.period.years) {
      deadline = addYears(deadline, selectedRule.period.years);
    }
    if (selectedRule.period.months) {
      deadline = addMonths(deadline, selectedRule.period.months);
    }

    const today = new Date();
    const daysRemaining = differenceInDays(deadline, today);
    const isExpired = isPast(deadline);

    setResult({ deadline, daysRemaining, isExpired });

};

return (

<div className="bg-white rounded-xl shadow-sm border p-6">
<h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
<Calendar className="w-5 h-5 text-blue-600" />
诉讼时效计算器
</h3>

      {/* 类型选择 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          选择时效类型
        </label>
        <select
          value={selectedRule?.id || ''}
          onChange={(e) => {
            const rule = LIMITATION_RULES.find(r => r.id === e.target.value);
            setSelectedRule(rule || null);
            setResult(null);
          }}
          className="w-full border rounded-lg p-2"
        >
          <option value="">请选择...</option>
          {Object.entries(
            LIMITATION_RULES.reduce((acc, rule) => {
              if (!acc[rule.category]) acc[rule.category] = [];
              acc[rule.category].push(rule);
              return acc;
            }, {} as Record<string, LimitationRule[]>)
          ).map(([category, rules]) => (
            <optgroup key={category} label={category}>
              {rules.map(rule => (
                <option key={rule.id} value={rule.id}>
                  {rule.name} ({rule.period.years ? `${rule.period.years}年` : ''}{rule.period.months ? `${rule.period.months}月` : ''})
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      {/* 规则说明 */}
      {selectedRule && (
        <div className="mb-4 p-3 bg-blue-50 rounded-lg text-sm">
          <p className="text-gray-700">{selectedRule.description}</p>
          <p className="text-gray-500 mt-1">
            法律依据：{selectedRule.legalBasis}
          </p>
          {selectedRule.notes && (
            <p className="text-orange-600 mt-1 flex items-start gap-1">
              <Info className="w-4 h-4 mt-0.5 flex-shrink-0" />
              {selectedRule.notes}
            </p>
          )}
        </div>
      )}

      {/* 起算日期 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          时效起算日期（知道或应当知道权利被侵害之日）
        </label>
        <input
          type="date"
          value={startDate}
          onChange={(e) => {
            setStartDate(e.target.value);
            setResult(null);
          }}
          className="w-full border rounded-lg p-2"
        />
      </div>

      {/* 计算按钮 */}
      <button
        onClick={calculate}
        disabled={!selectedRule || !startDate}
        className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        计算时效
      </button>

      {/* 结果展示 */}
      {result && (
        <div className={`mt-4 p-4 rounded-lg ${
          result.isExpired
            ? 'bg-red-50 border border-red-200'
            : result.daysRemaining <= 30
              ? 'bg-yellow-50 border border-yellow-200'
              : 'bg-green-50 border border-green-200'
        }`}>
          <div className="flex items-start gap-3">
            {result.isExpired ? (
              <AlertTriangle className="w-6 h-6 text-red-600 flex-shrink-0" />
            ) : (
              <CheckCircle className={`w-6 h-6 flex-shrink-0 ${
                result.daysRemaining <= 30 ? 'text-yellow-600' : 'text-green-600'
              }`} />
            )}

            <div>
              <p className="font-medium">
                诉讼时效截止日期：{format(result.deadline, 'yyyy年MM月dd日')}
              </p>

              {result.isExpired ? (
                <p className="text-red-600 mt-1">
                  ⚠️ 时效已过期 {Math.abs(result.daysRemaining)} 天
                </p>
              ) : (
                <p className={`mt-1 ${
                  result.daysRemaining <= 30 ? 'text-yellow-700' : 'text-green-700'
                }`}>
                  距离时效届满还有 <strong>{result.daysRemaining}</strong> 天
                  {result.daysRemaining <= 30 && '，请尽快采取行动！'}
                </p>
              )}

              <p className="text-xs text-gray-500 mt-2">
                * 以上仅供参考，实际时效可能因中止、中断等情形变化，建议咨询律师确认
              </p>
            </div>
          </div>
        </div>
      )}
    </div>

);
};
法律费用估算器
TypeScript

// frontend/src/components/tools/LegalFeeEstimator.tsx

import { useState } from 'react';
import { Calculator, DollarSign, Info } from 'lucide-react';

interface FeeBreakdown {
courtFee: number; // 诉讼费
lawyerFee: number; // 律师费估算
appraisalFee?: number; // 鉴定费
preservationFee?: number; // 保全费
executionFee?: number; // 执行费
otherFees?: number; // 其他费用
total: number;
}

type CaseType = 'property' | 'labor' | 'divorce' | 'personal_injury' | 'contract';

export const LegalFeeEstimator: React.FC = () => {
const [caseType, setCaseType] = useState<CaseType>('property');
const [amount, setAmount] = useState<number>(0);
const [needsLawyer, setNeedsLawyer] = useState(true);
const [needsPreservation, setNeedsPreservation] = useState(false);
const [result, setResult] = useState<FeeBreakdown | null>(null);

// 诉讼费计算（根据《诉讼费用交纳办法》）
const calculateCourtFee = (type: CaseType, disputeAmount: number): number => {
if (type === 'labor') {
return 10; // 劳动争议案件 10 元
}

    if (type === 'divorce') {
      // 离婚案件：每件50-300元；涉及财产分割超过20万的部分按0.5%
      let fee = 150; // 基础费用
      if (disputeAmount > 200000) {
        fee += (disputeAmount - 200000) * 0.005;
      }
      return fee;
    }

    // 财产案件阶梯计算
    if (disputeAmount <= 10000) {
      return 50;
    } else if (disputeAmount <= 100000) {
      return 50 + (disputeAmount - 10000) * 0.025;
    } else if (disputeAmount <= 200000) {
      return 2300 + (disputeAmount - 100000) * 0.02;
    } else if (disputeAmount <= 500000) {
      return 4300 + (disputeAmount - 200000) * 0.015;
    } else if (disputeAmount <= 1000000) {
      return 8800 + (disputeAmount - 500000) * 0.01;
    } else if (disputeAmount <= 2000000) {
      return 13800 + (disputeAmount - 1000000) * 0.009;
    } else if (disputeAmount <= 5000000) {
      return 22800 + (disputeAmount - 2000000) * 0.008;
    } else if (disputeAmount <= 10000000) {
      return 46800 + (disputeAmount - 5000000) * 0.007;
    } else if (disputeAmount <= 20000000) {
      return 81800 + (disputeAmount - 10000000) * 0.006;
    } else {
      return 141800 + (disputeAmount - 20000000) * 0.005;
    }

};

// 律师费估算（按当地市场行情）
const estimateLawyerFee = (type: CaseType, disputeAmount: number): number => {
// 简单估算：基础费用 + 风险代理比例
const baseFee = 5000;

    if (disputeAmount <= 100000) {
      return baseFee + disputeAmount * 0.05;
    } else if (disputeAmount <= 500000) {
      return baseFee + 5000 + (disputeAmount - 100000) * 0.04;
    } else if (disputeAmount <= 1000000) {
      return baseFee + 21000 + (disputeAmount - 500000) * 0.03;
    } else {
      return baseFee + 36000 + (disputeAmount - 1000000) * 0.02;
    }

};

// 保全费计算
const calculatePreservationFee = (preserveAmount: number): number => {
if (preserveAmount <= 1000) {
return 30;
} else if (preserveAmount <= 100000) {
return 30 + (preserveAmount - 1000) _ 0.01;
} else {
return 1020 + (preserveAmount - 100000) _ 0.005;
}
};

const calculate = () => {
const courtFee = calculateCourtFee(caseType, amount);
const lawyerFee = needsLawyer ? estimateLawyerFee(caseType, amount) : 0;
const preservationFee = needsPreservation ? calculatePreservationFee(amount) : 0;

    const total = courtFee + lawyerFee + preservationFee;

    setResult({
      courtFee,
      lawyerFee,
      preservationFee: needsPreservation ? preservationFee : undefined,
      total,
    });

};

return (

<div className="bg-white rounded-xl shadow-sm border p-6">
<h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
<Calculator className="w-5 h-5 text-blue-600" />
法律费用估算器
</h3>

      {/* 案件类型 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          案件类型
        </label>
        <select
          value={caseType}
          onChange={(e) => setCaseType(e.target.value as CaseType)}
          className="w-full border rounded-lg p-2"
        >
          <option value="property">财产纠纷（合同、债务等）</option>
          <option value="labor">劳动争议</option>
          <option value="divorce">离婚纠纷</option>
          <option value="personal_injury">人身损害赔偿</option>
        </select>
      </div>

      {/* 争议金额 */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          争议金额（元）
        </label>
        <input
          type="number"
          value={amount || ''}
          onChange={(e) => setAmount(Number(e.target.value))}
          placeholder="请输入争议标的金额"
          className="w-full border rounded-lg p-2"
        />
      </div>

      {/* 可选项 */}
      <div className="mb-4 space-y-2">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={needsLawyer}
            onChange={(e) => setNeedsLawyer(e.target.checked)}
          />
          <span className="text-sm">需要聘请律师</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={needsPreservation}
            onChange={(e) => setNeedsPreservation(e.target.checked)}
          />
          <span className="text-sm">需要财产保全</span>
        </label>
      </div>

      {/* 计算按钮 */}
      <button
        onClick={calculate}
        disabled={!amount}
        className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        估算费用
      </button>

      {/* 结果 */}
      {result && (
        <div className="mt-4 p-4 bg-gray-50 rounded-lg">
          <h4 className="font-medium mb-3">费用明细（估算）</h4>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span>诉讼费</span>
              <span>¥{result.courtFee.toLocaleString()}</span>
            </div>

            {result.lawyerFee > 0 && (
              <div className="flex justify-between">
                <span>律师费（估算）</span>
                <span>¥{result.lawyerFee.toLocaleString()}</span>
              </div>
            )}

            {result.preservationFee && (
              <div className="flex justify-between">
                <span>财产保全费</span>
                <span>¥{result.preservationFee.toLocaleString()}</span>
              </div>
            )}

            <div className="border-t pt-2 flex justify-between font-semibold">
              <span>预估总费用</span>
              <span className="text-blue-600">¥{result.total.toLocaleString()}</span>
            </div>
          </div>

          <p className="text-xs text-gray-500 mt-3 flex items-start gap-1">
            <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
            以上费用仅供参考，实际费用可能因地区、案件复杂程度等因素有所不同
          </p>
        </div>
      )}
    </div>

);
};
1.4 对话管理增强
对话历史搜索
TypeScript

// frontend/src/components/chat/ChatHistorySearch.tsx

import { useState, useMemo, useCallback } from 'react';
import { Search, Calendar, MessageSquare, Filter, X } from 'lucide-react';
import { debounce } from 'lodash';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';

interface ChatSession {
id: string;
title: string;
preview: string;
messageCount: number;
createdAt: Date;
updatedAt: Date;
tags?: string[];
}

export const ChatHistorySearch: React.FC<{
sessions: ChatSession[];
onSelect: (sessionId: string) => void;
}> = ({ sessions, onSelect }) => {
const [searchTerm, setSearchTerm] = useState('');
const [dateFilter, setDateFilter] = useState<'all' | 'today' | 'week' | 'month'>('all');
const [isOpen, setIsOpen] = useState(false);

const filteredSessions = useMemo(() => {
let result = sessions;

    // 日期过滤
    if (dateFilter !== 'all') {
      const now = new Date();
      const filterDate = {
        today: new Date(now.setHours(0, 0, 0, 0)),
        week: new Date(now.setDate(now.getDate() - 7)),
        month: new Date(now.setMonth(now.getMonth() - 1)),
      }[dateFilter];

      result = result.filter(s => new Date(s.updatedAt) >= filterDate);
    }

    // 搜索过滤
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(s =>
        s.title.toLowerCase().includes(term) ||
        s.preview.toLowerCase().includes(term)
      );
    }

    return result.sort((a, b) =>
      new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );

}, [sessions, searchTerm, dateFilter]);

const debouncedSearch = useCallback(
debounce((term: string) => setSearchTerm(term), 300),
[]
);

return (

<div className="relative">
{/_ 搜索触发器 _/}
<button
onClick={() => setIsOpen(true)}
className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg" >
<Search className="w-4 h-4" />
搜索历史对话
</button>

      {/* 搜索面板 */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-96 bg-white rounded-xl shadow-lg border z-50">
          {/* 搜索框 */}
          <div className="p-3 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="搜索对话内容..."
                onChange={(e) => debouncedSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border rounded-lg"
                autoFocus
              />
            </div>

            {/* 日期过滤 */}
            <div className="flex gap-2 mt-2">
              {(['all', 'today', 'week', 'month'] as const).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setDateFilter(filter)}
                  className={`text-xs px-2 py-1 rounded ${
                    dateFilter === filter
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {{ all: '全部', today: '今天', week: '本周', month: '本月' }[filter]}
                </button>
              ))}
            </div>
          </div>

          {/* 结果列表 */}
          <div className="max-h-96 overflow-y-auto">
            {filteredSessions.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                未找到相关对话
              </div>
            ) : (
              filteredSessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => {
                    onSelect(session.id);
                    setIsOpen(false);
                  }}
                  className="w-full p-3 text-left hover:bg-gray-50 border-b last:border-b-0"
                >
                  <div className="flex items-start justify-between">
                    <h4 className="font-medium text-sm truncate flex-1">
                      {session.title}
                    </h4>
                    <span className="text-xs text-gray-400 ml-2">
                      {formatDistanceToNow(new Date(session.updatedAt), {
                        addSuffix: true,
                        locale: zhCN,
                      })}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                    {session.preview}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-400 flex items-center gap-1">
                      <MessageSquare className="w-3 h-3" />
                      {session.messageCount} 条消息
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>

          {/* 关闭按钮 */}
          <button
            onClick={() => setIsOpen(false)}
            className="absolute top-2 right-2 p-1 text-gray-400 hover:text-gray-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>

);
};
二、后端功能扩展
2.1 语音处理接口
Python

# backend/app/routers/ai.py

from fastapi import UploadFile, File
import tempfile
import os

@router.post("/speech-to-text")
async def speech_to_text(
audio: UploadFile = File(...),
current_user: User | None = Depends(get_current_user_optional)
):
"""
语音转文字
支持格式：webm, wav, mp3, m4a
""" # 验证文件类型
allowed_types = ['audio/webm', 'audio/wav', 'audio/mpeg', 'audio/mp4']
if audio.content_type not in allowed_types:
raise HTTPException(400, "不支持的音频格式")

    # 限制文件大小（10MB）
    contents = await audio.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件过大，最大支持10MB")

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # 调用语音识别服务
        # 方案1：使用 OpenAI Whisper API
        transcript = await transcribe_with_whisper(tmp_path)

        # 方案2：使用本地 Whisper 模型
        # transcript = await transcribe_with_local_whisper(tmp_path)

        return {"text": transcript, "duration": len(contents) / 1024}  # 估算
    finally:
        os.unlink(tmp_path)

async def transcribe_with_whisper(audio_path: str) -> str:
"""使用 OpenAI Whisper API 转写"""
import openai

    client = openai.OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url
    )

    with open(audio_path, 'rb') as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="zh"
        )

    return transcript.text

@router.post("/text-to-speech")
async def text_to_speech(
request: TextToSpeechRequest,
current_user: User | None = Depends(get_current_user_optional)
):
"""
文字转语音
""" # 限制文本长度
if len(request.text) > 2000:
raise HTTPException(400, "文本过长，最大支持 2000 字")

    # 调用 TTS 服务
    audio_data = await generate_speech(
        request.text,
        voice=request.voice or "alloy",
        speed=request.speed or 1.0
    )

    return StreamingResponse(
        io.BytesIO(audio_data),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "attachment; filename=speech.mp3"}
    )

2.2 文件分析接口
Python

# backend/app/routers/ai.py

from pdf2image import convert_from_bytes
import pytesseract
from docx import Document
import io

@router.post("/analyze-file")
async def analyze_file(
file: UploadFile = File(...),
current_user: User = Depends(get_current_user)
):
"""
分析上传的文件（合同、证据等）
返回：文件类型识别、关键信息提取、相关问题建议
""" # 验证文件
allowed_types = {
'application/pdf': 'pdf',
'image/png': 'image',
'image/jpeg': 'image',
'application/msword': 'doc',
'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
}

    file_type = allowed_types.get(file.content_type)
    if not file_type:
        raise HTTPException(400, "不支持的文件格式")

    contents = await file.read()

    # 限制大小（20MB）
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "文件过大")

    # 提取文本
    extracted_text = await extract_text(contents, file_type)

    # 使用 LLM 分析文件
    analysis = await analyze_document_with_llm(extracted_text, file.filename)

    return {
        "file_type": analysis.document_type,
        "extracted_text": extracted_text[:1000] + "..." if len(extracted_text) > 1000 else extracted_text,
        "key_points": analysis.key_points,
        "potential_issues": analysis.potential_issues,
        "suggested_questions": analysis.suggested_questions,
    }

async def extract_text(contents: bytes, file_type: str) -> str:
"""从文件中提取文本"""
if file_type == 'pdf': # 尝试直接提取文字
import fitz # PyMuPDF
doc = fitz.open(stream=contents, filetype="pdf")
text = ""
for page in doc:
text += page.get_text()

        # 如果文字太少，可能是扫描件，用 OCR
        if len(text.strip()) < 100:
            images = convert_from_bytes(contents)
            text = "\n".join(pytesseract.image_to_string(img, lang='chi_sim') for img in images)

        return text

    elif file_type == 'image':
        from PIL import Image
        img = Image.open(io.BytesIO(contents))
        return pytesseract.image_to_string(img, lang='chi_sim')

    elif file_type == 'docx':
        doc = Document(io.BytesIO(contents))
        return "\n".join(para.text for para in doc.paragraphs)

    elif file_type == 'doc':
        # 需要额外处理，使用 antiword 或转换
        raise HTTPException(400, "请上传 .docx 格式的文件")

    return ""

async def analyze_document_with_llm(text: str, filename: str) -> DocumentAnalysis:
"""使用 LLM 分析文档"""
prompt = f"""
分析以下法律相关文件，返回 JSON 格式结果：

    文件名：{filename}

    文件内容：
    {text[:5000]}

    请分析并返回：
    {{
        "document_type": "文档类型（如：劳动合同、借款协议、起诉状、证据材料等）",
        "key_points": ["关键信息点1", "关键信息点2", ...],
        "potential_issues": ["潜在法律问题1", "潜在法律问题2", ...],
        "suggested_questions": ["建议咨询的问题1", "建议咨询的问题2", ...]
    }}
    """

    # 调用 LLM
    response = await llm.ainvoke(prompt)

    # 解析结果
    return DocumentAnalysis.model_validate_json(response.content)

2.3 知识库管理接口
Python

# backend/app/routers/admin/knowledge.py

from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from typing import List

router = APIRouter(prefix="/admin/knowledge", tags=["知识库管理"])

@router.get("/stats")
async def get_knowledge_stats(
admin: User = Depends(require_admin)
):
"""获取知识库统计信息"""
kb = get_knowledge_base()

    collection = kb.vectorstore._collection
    count = collection.count()

    # 获取各类别分布
    results = collection.get(include=["metadatas"])
    categories = {}
    for meta in results.get("metadatas", []):
        cat = meta.get("category", "未分类")
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "total_documents": count,
        "categories": categories,
        "last_updated": kb.last_updated,
        "embedding_model": settings.embedding_model,
    }

@router.post("/import")
async def import_knowledge(
background_tasks: BackgroundTasks,
file: UploadFile = File(...),
category: str = Form(...),
admin: User = Depends(require_admin)
):
"""
批量导入法律知识
支持格式：JSON, CSV, TXT
"""
contents = await file.read()

    # 验证和解析文件
    if file.filename.endswith('.json'):
        data = json.loads(contents)
    elif file.filename.endswith('.csv'):
        import csv
        reader = csv.DictReader(io.StringIO(contents.decode()))
        data = list(reader)
    else:
        raise HTTPException(400, "不支持的文件格式")

    # 创建导入任务
    task_id = str(uuid.uuid4())

    background_tasks.add_task(
        process_knowledge_import,
        task_id=task_id,
        data=data,
        category=category,
        admin_id=admin.id
    )

    return {"task_id": task_id, "status": "processing", "total": len(data)}

@router.get("/import/{task_id}/status")
async def get_import_status(
task_id: str,
admin: User = Depends(require_admin)
):
"""获取导入任务状态"""
status = await get_task_status(task_id)
return status

@router.post("/sync-laws")
async def sync_laws_from_source(
background_tasks: BackgroundTasks,
source: str = Query(..., description="来源：pkulaw|cnlaw"),
admin: User = Depends(require_admin)
):
"""从法律数据源同步最新法条"""
task_id = str(uuid.uuid4())

    background_tasks.add_task(
        sync_laws_task,
        task_id=task_id,
        source=source
    )

    return {"task_id": task_id, "status": "processing"}

@router.delete("/documents")
async def delete_documents(
document_ids: List[str],
admin: User = Depends(require_admin)
):
"""删除指定知识条目"""
kb = get_knowledge_base()
kb.vectorstore.\_collection.delete(ids=document_ids)

    return {"deleted": len(document_ids)}

@router.post("/rebuild-index")
async def rebuild_index(
background_tasks: BackgroundTasks,
admin: User = Depends(require_admin)
):
"""重建向量索引"""
task_id = str(uuid.uuid4())

    background_tasks.add_task(
        rebuild_vector_index,
        task_id=task_id
    )

    return {"task_id": task_id, "status": "processing"}

2.4 对话质量评估与分析
Python

# backend/app/services/quality_analysis.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import Counter
import jieba
import jieba.analyse

@dataclass
class QualityMetrics:
total_sessions: int
total_messages: int
avg_session_length: float
rated_responses: int
positive_rate: float
negative_rate: float
neutral_rate: float
avg_response_time: float # 秒

@dataclass
class TopicAnalysis:
top_keywords: list[tuple[str, float]]
top_legal_domains: list[tuple[str, int]]
trending_topics: list[tuple[str, int]]

class ConversationAnalyzer:
"""对话分析服务"""

    def __init__(self, db: Session):
        self.db = db

    async def get_quality_metrics(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> QualityMetrics:
        """获取质量指标"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()

        # 查询统计
        sessions = await self.db.execute(
            select(Consultation)
            .where(Consultation.created_at.between(start_date, end_date))
        )
        sessions = sessions.scalars().all()

        messages = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.created_at.between(start_date, end_date))
        )
        messages = messages.scalars().all()

        # 计算评价分布
        rated = [m for m in messages if m.rating is not None and m.role == 'assistant']
        positive = sum(1 for m in rated if m.rating == 3)
        negative = sum(1 for m in rated if m.rating == 1)
        neutral = sum(1 for m in rated if m.rating == 2)
        total_rated = len(rated)

        return QualityMetrics(
            total_sessions=len(sessions),
            total_messages=len(messages),
            avg_session_length=len(messages) / max(len(sessions), 1),
            rated_responses=total_rated,
            positive_rate=positive / max(total_rated, 1),
            negative_rate=negative / max(total_rated, 1),
            neutral_rate=neutral / max(total_rated, 1),
            avg_response_time=0,  # TODO: 需要记录响应时间
        )

    async def analyze_topics(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> TopicAnalysis:
        """分析热门话题"""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()

        # 获取用户消息
        messages = await self.db.execute(
            select(ChatMessage.content)
            .where(
                ChatMessage.created_at.between(start_date, end_date),
                ChatMessage.role == 'user'
            )
        )
        user_messages = [m[0] for m in messages]

        # 合并文本
        all_text = " ".join(user_messages)

        # 提取关键词
        keywords = jieba.analyse.extract_tags(all_text, topK=20, withWeight=True)

        # 法律领域分类
        domain_keywords = {
            "劳动纠纷": ["工资", "辞退", "社保", "加班", "劳动合同", "工伤"],
            "合同纠纷": ["合同", "违约", "定金", "押金", "赔偿"],
            "婚姻家庭": ["离婚", "抚养", "财产分割", "继承", "遗产"],
            "借贷纠纷": ["借款", "欠钱", "利息", "还款", "债务"],
            "房产纠纷": ["房子", "租房", "房东", "买房", "物业"],
            "交通事故": ["车祸", "交通", "肇事", "理赔", "保险"],
        }

        domain_counts = Counter()
        for msg in user_messages:
            for domain, kws in domain_keywords.items():
                if any(kw in msg for kw in kws):
                    domain_counts[domain] += 1

        return TopicAnalysis(
            top_keywords=keywords,
            top_legal_domains=domain_counts.most_common(10),
            trending_topics=self._find_trending(user_messages),
        )

    def _find_trending(self, messages: list[str]) -> list[tuple[str, int]]:
        """发现趋势话题（简单实现）"""
        # 使用 n-gram 或更复杂的话题模型
        # 这里简单返回高频词
        from collections import Counter
        words = []
        for msg in messages:
            words.extend(jieba.cut(msg))

        # 过滤停用词
        stopwords = {'的', '了', '是', '我', '有', '在', '不', '吗', '怎么', '什么'}
        words = [w for w in words if w not in stopwords and len(w) > 1]

        return Counter(words).most_common(20)

@router.get("/admin/ai/analytics/quality")
async def get_quality_analytics(
days: int = Query(7, ge=1, le=90),
admin: User = Depends(require_admin),
db: Session = Depends(get_db)
):
"""获取 AI 质量分析数据"""
analyzer = ConversationAnalyzer(db)

    start_date = datetime.utcnow() - timedelta(days=days)

    metrics = await analyzer.get_quality_metrics(start_date)
    topics = await analyzer.analyze_topics(start_date)

    return {
        "metrics": metrics,
        "topics": topics,
        "period": {"start": start_date, "end": datetime.utcnow()},
    }

2.5 FAQ 自动生成
Python

# backend/app/services/faq_generator.py

from typing import List
from pydantic import BaseModel

class FAQItem(BaseModel):
question: str
answer: str
category: str
popularity: int
created_from_session_ids: List[str]

class FAQGeneratorService:
"""基于历史对话自动生成 FAQ"""

    def __init__(self, db: Session, llm):
        self.db = db
        self.llm = llm

    async def generate_faqs(
        self,
        min_sessions: int = 5,
        time_range_days: int = 30
    ) -> List[FAQItem]:
        """
        分析历史对话，生成FAQ
        1. 聚类相似问题
        2. 提取代表性问答对
        3. 优化答案表述
        """
        start_date = datetime.utcnow() - timedelta(days=time_range_days)

        # 获取高质量回答（评分>=2的）
        quality_conversations = await self.db.execute(
            select(Consultation)
            .join(ChatMessage)
            .where(
                Consultation.created_at >= start_date,
                ChatMessage.role == 'assistant',
                ChatMessage.rating >= 2
            )
            .options(selectinload(Consultation.messages))
        )
        conversations = quality_conversations.scalars().unique().all()

        # 提取问答对
        qa_pairs = []
        for conv in conversations:
            messages = sorted(conv.messages, key=lambda m: m.created_at)
            for i in range(0, len(messages) - 1, 2):
                if messages[i].role == 'user' and messages[i+1].role == 'assistant':
                    qa_pairs.append({
                        "question": messages[i].content,
                        "answer": messages[i+1].content,
                        "session_id": conv.session_id,
                        "rating": messages[i+1].rating or 0,
                    })

        # 聚类相似问题
        clusters = await self._cluster_questions([q["question"] for q in qa_pairs])

        # 为每个聚类生成FAQ
        faqs = []
        for cluster in clusters:
            if len(cluster["questions"]) >= min_sessions:
                faq = await self._generate_faq_for_cluster(cluster, qa_pairs)
                if faq:
                    faqs.append(faq)

        return faqs

    async def _cluster_questions(self, questions: List[str]) -> List[dict]:
        """聚类相似问题"""
        from sklearn.cluster import KMeans
        from sentence_transformers import SentenceTransformer

        # 获取向量
        model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        embeddings = model.encode(questions)

        # KMeans 聚类
        n_clusters = min(len(questions) // 5, 50)  # 动态确定聚类数
        if n_clusters < 2:
            return [{"questions": questions, "indices": list(range(len(questions)))}]

        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(embeddings)

        # 整理聚类结果
        clusters = {}
        for idx, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = {"questions": [], "indices": []}
            clusters[label]["questions"].append(questions[idx])
            clusters[label]["indices"].append(idx)

        return list(clusters.values())

    async def _generate_faq_for_cluster(
        self,
        cluster: dict,
        qa_pairs: List[dict]
    ) -> FAQItem | None:
        """为一个聚类生成FAQ"""
        # 获取该聚类的问答对
        cluster_qas = [qa_pairs[i] for i in cluster["indices"]]

        # 选择评分最高的答案作为基础
        best_qa = max(cluster_qas, key=lambda x: x["rating"])

        # 使用 LLM 优化
        prompt = f"""
        基于以下相似问题和答案，生成一个标准化的FAQ：

        相似问题：
        {chr(10).join(f'- {q}' for q in cluster["questions"][:5])}

        参考答案：
        {best_qa["answer"][:1000]}

        请生成：
        1. 一个通用化的问题（简洁明了）
        2. 一个标准化的答案（专业、完整、200字以内）
        3. 问题分类（劳动/合同/婚姻/借贷/房产/其他）

        返回JSON：
        {{"question": "...", "answer": "...", "category": "..."}}
        """

        response = await self.llm.ainvoke(prompt)
        result = json.loads(response.content)

        return FAQItem(
            question=result["question"],
            answer=result["answer"],
            category=result["category"],
            popularity=len(cluster["questions"]),
            created_from_session_ids=[qa["session_id"] for qa in cluster_qas],
        )

@router.post("/admin/ai/faq/generate")
async def generate_faqs(
background_tasks: BackgroundTasks,
admin: User = Depends(require_admin),
db: Session = Depends(get_db)
):
"""触发 FAQ 自动生成"""
task_id = str(uuid.uuid4())

    background_tasks.add_task(
        run_faq_generation,
        task_id=task_id,
        db=db
    )

    return {"task_id": task_id, "status": "processing"}

@router.get("/faqs")
async def get_faqs(
category: str = None,
limit: int = Query(20, le=100),
db: Session = Depends(get_db)
):
"""获取 FAQ 列表（公开接口）"""
query = select(FAQ).where(FAQ.is_published == True)

    if category:
        query = query.where(FAQ.category == category)

    query = query.order_by(FAQ.popularity.desc()).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()

2.6 多模型支持与 Fallback
Python

# backend/app/services/model_router.py

from enum import Enum
from typing import Optional
import asyncio

class ModelProvider(Enum):
OPENAI = "openai"
DEEPSEEK = "deepseek"
QWEN = "qwen"
LOCAL = "local"

class ModelConfig:
def **init**(
self,
provider: ModelProvider,
model_name: str,
api_key: str,
base_url: str,
max_tokens: int = 2000,
temperature: float = 0.7,
priority: int = 1,
cost_per_1k_tokens: float = 0.0
):
self.provider = provider
self.model_name = model_name
self.api_key = api_key
self.base_url = base_url
self.max_tokens = max_tokens
self.temperature = temperature
self.priority = priority
self.cost_per_1k_tokens = cost_per_1k_tokens

class ModelRouter:
"""模型路由器 - 支持多模型切换和降级"""

    def __init__(self):
        self.models: dict[str, ModelConfig] = {}
        self.health_status: dict[str, bool] = {}
        self._load_configs()

    def _load_configs(self):
        """加载模型配置"""
        # 主模型：DeepSeek
        if settings.deepseek_api_key:
            self.models["deepseek"] = ModelConfig(
                provider=ModelProvider.DEEPSEEK,
                model_name="deepseek-chat",
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com/v1",
                priority=1,
                cost_per_1k_tokens=0.001
            )

        # 备用模型：通义千问
        if settings.qwen_api_key:
            self.models["qwen"] = ModelConfig(
                provider=ModelProvider.QWEN,
                model_name="qwen-turbo",
                api_key=settings.qwen_api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                priority=2,
                cost_per_1k_tokens=0.002
            )

        # OpenAI 作为最后备用
        if settings.openai_api_key:
            self.models["openai"] = ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-3.5-turbo",
                api_key=settings.openai_api_key,
                base_url="https://api.openai.com/v1",
                priority=3,
                cost_per_1k_tokens=0.002
            )

    async def get_available_model(self) -> Optional[ModelConfig]:
        """获取可用模型（按优先级）"""
        sorted_models = sorted(
            self.models.values(),
            key=lambda m: m.priority
        )

        for model in sorted_models:
            if self.health_status.get(model.model_name, True):
                return model

        return None

    async def invoke(
        self,
        messages: list[dict],
        stream: bool = False,
        **kwargs
    ):
        """调用模型（带自动降级）"""
        sorted_models = sorted(
            self.models.values(),
            key=lambda m: m.priority
        )

        last_error = None
        for model in sorted_models:
            if not self.health_status.get(model.model_name, True):
                continue

            try:
                result = await self._call_model(model, messages, stream, **kwargs)
                return result
            except Exception as e:
                last_error = e
                # 标记模型不健康
                self.health_status[model.model_name] = False
                # 启动后台健康检查
                asyncio.create_task(self._health_check(model))
                continue

        raise last_error or Exception("No available model")

    async def _call_model(
        self,
        config: ModelConfig,
        messages: list[dict],
        stream: bool,
        **kwargs
    ):
        """调用具体模型"""
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=config.model_name,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            **kwargs
        )

        if stream:
            return llm.astream(messages)
        else:
            return await llm.ainvoke(messages)

    async def _health_check(self, config: ModelConfig, retry_after: int = 60):
        """后台健康检查"""
        await asyncio.sleep(retry_after)

        try:
            # 发送简单测试请求
            await self._call_model(
                config,
                [{"role": "user", "content": "test"}],
                stream=False
            )
            self.health_status[config.model_name] = True
        except:
            # 继续标记为不健康，稍后重试
            asyncio.create_task(self._health_check(config, retry_after * 2))

# 使用示例

model_router = ModelRouter()

@router.post("/chat")
async def chat(request: ChatRequest):
model = await model_router.get_available_model()
if not model:
raise HTTPException(503, "暂无可用的 AI 服务")

    response = await model_router.invoke(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.message}
        ]
    )

    return {"answer": response.content, "model_used": model.model_name}

三、全栈联动功能
3.1 实时在线律师对接
Python

# backend/app/routers/ai.py

@router.post("/consultations/{session_id}/request-lawyer")
async def request_lawyer_assistance(
session_id: str,
request: LawyerAssistanceRequest,
current_user: User = Depends(get_current_user),
db: Session = Depends(get_db)
):
"""
请求律师介入当前 AI 对话 1. 生成对话摘要 2. 匹配在线律师 3. 创建转接请求 4. 通知律师（WebSocket）
""" # 验证会话
consultation = await get_consultation_or_404(db, session_id, current_user)

    # 生成对话摘要
    summary = await generate_consultation_summary(consultation)

    # 查找在线律师
    online_lawyers = await find_online_lawyers(
        specialties=summary.detected_domains,
        location=request.preferred_location
    )

    if not online_lawyers:
        return {
            "status": "no_available_lawyer",
            "message": "当前没有匹配的在线律师，您可以预约咨询",
            "alternatives": await get_lawyer_recommendations(summary)
        }

    # 创建转接请求
    transfer_request = await create_transfer_request(
        consultation_id=consultation.id,
        user_id=current_user.id,
        summary=summary,
        target_lawyers=[l.id for l in online_lawyers[:3]]
    )

    # 通过 WebSocket 通知律师
    for lawyer in online_lawyers[:3]:
        await notify_lawyer(lawyer.id, {
            "type": "transfer_request",
            "request_id": transfer_request.id,
            "user_name": current_user.nickname or "用户",
            "summary": summary.brief,
            "urgency": request.urgency
        })

    return {
        "status": "pending",
        "request_id": transfer_request.id,
        "estimated_wait_time": "1-3分钟",
        "matched_lawyers": len(online_lawyers)
    }

TypeScript

// frontend/src/components/chat/LawyerHandoffPanel.tsx

import { useState, useEffect } from 'react';
import { User, Clock, CheckCircle, XCircle } from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';

interface LawyerHandoffPanelProps {
sessionId: string;
onHandoffComplete: (lawyerId: string) => void;
}

export const LawyerHandoffPanel: React.FC<LawyerHandoffPanelProps> = ({
sessionId,
onHandoffComplete,
}) => {
const [status, setStatus] = useState<'idle' | 'requesting' | 'waiting' | 'connected' | 'failed'>('idle');
const [requestId, setRequestId] = useState<string | null>(null);
const [matchedLawyers, setMatchedLawyers] = useState(0);
const [waitTime, setWaitTime] = useState(0);

const { lastMessage } = useWebSocket('/ws/user');

// 监听 WebSocket 消息
useEffect(() => {
if (lastMessage?.type === 'lawyer_accepted') {
setStatus('connected');
onHandoffComplete(lastMessage.lawyer_id);
} else if (lastMessage?.type === 'request_timeout') {
setStatus('failed');
}
}, [lastMessage]);

// 等待计时
useEffect(() => {
if (status === 'waiting') {
const timer = setInterval(() => setWaitTime(t => t + 1), 1000);
return () => clearInterval(timer);
}
}, [status]);

const requestLawyer = async () => {
setStatus('requesting');

    try {
      const response = await fetch(`/api/ai/consultations/${sessionId}/request-lawyer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urgency: 'normal' }),
      });

      const data = await response.json();

      if (data.status === 'pending') {
        setStatus('waiting');
        setRequestId(data.request_id);
        setMatchedLawyers(data.matched_lawyers);
      } else {
        setStatus('failed');
      }
    } catch (error) {
      setStatus('failed');
    }

};

const cancelRequest = async () => {
if (requestId) {
await fetch(`/api/ai/transfer-requests/${requestId}/cancel`, { method: 'POST' });
}
setStatus('idle');
setRequestId(null);
};

return (

<div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-200">
{status === 'idle' && (
<div className="text-center">
<User className="w-12 h-12 mx-auto text-blue-600 mb-3" />
<h3 className="font-semibold mb-2">需要专业律师帮助？</h3>
<p className="text-sm text-gray-600 mb-4">
AI 助手可以回答常见问题，但复杂情况建议咨询真人律师
</p>
<button
            onClick={requestLawyer}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
          >
连线在线律师
</button>
</div>
)}

      {status === 'requesting' && (
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-3" />
          <p>正在匹配律师...</p>
        </div>
      )}

      {status === 'waiting' && (
        <div className="text-center">
          <Clock className="w-12 h-12 mx-auto text-orange-500 mb-3 animate-pulse" />
          <h3 className="font-semibold mb-2">正在等待律师接听</h3>
          <p className="text-sm text-gray-600 mb-2">
            已匹配 {matchedLawyers} 位在线律师
          </p>
          <p className="text-lg font-mono mb-4">
            等待时间：{Math.floor(waitTime / 60)}:{(waitTime % 60).toString().padStart(2, '0')}
          </p>
          <button
            onClick={cancelRequest}
            className="text-gray-600 hover:text-gray-900 text-sm"
          >
            取消请求
          </button>
        </div>
      )}

      {status === 'connected' && (
        <div className="text-center">
          <CheckCircle className="w-12 h-12 mx-auto text-green-500 mb-3" />
          <h3 className="font-semibold text-green-700">已连接律师</h3>
          <p className="text-sm text-gray-600">正在跳转到对话页面...</p>
        </div>
      )}

      {status === 'failed' && (
        <div className="text-center">
          <XCircle className="w-12 h-12 mx-auto text-red-500 mb-3" />
          <h3 className="font-semibold mb-2">暂时没有可用律师</h3>
          <p className="text-sm text-gray-600 mb-4">
            您可以预约咨询或稍后再试
          </p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => setStatus('idle')}
              className="px-4 py-2 border rounded-lg hover:bg-gray-50"
            >
              重试
            </button>
            <button
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              预约咨询
            </button>
          </div>
        </div>
      )}
    </div>

);
};

3.2 咨询报告导出（PDF/Word）
Python

# backend/app/services/report_generator.py

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from datetime import datetime
from dataclasses import dataclass
from typing import List

# 注册中文字体

pdfmetrics.registerFont(TTFont('SimSun', 'fonts/simsun.ttc'))

@dataclass
class ConsultationReport:
session_id: str
user_name: str
created_at: datetime
summary: str
legal_domains: List[str]
key_issues: List[str]
legal_analysis: str
risk_assessment: List[dict]
recommendations: List[str]
referenced_laws: List[dict]
messages: List[dict]
disclaimer: str

class PDFReportGenerator:
"""PDF 报告生成器"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_chinese_styles()

    def _setup_chinese_styles(self):
        """设置中文样式"""
        self.styles.add(ParagraphStyle(
            name='ChineseTitle',
            fontName='SimSun',
            fontSize=18,
            leading=24,
            alignment=1,  # 居中
            spaceAfter=20
        ))
        self.styles.add(ParagraphStyle(
            name='ChineseHeading',
            fontName='SimSun',
            fontSize=14,
            leading=20,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor('#1a56db')
        ))
        self.styles.add(ParagraphStyle(
            name='ChineseBody',
            fontName='SimSun',
            fontSize=10,
            leading=16,
            spaceAfter=8
        ))
        self.styles.add(ParagraphStyle(
            name='ChineseSmall',
            fontName='SimSun',
            fontSize=8,
            leading=12,
            textColor=colors.grey
        ))

    def generate(self, report: ConsultationReport) -> bytes:
        """生成 PDF 报告"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )

        story = []

        # 标题
        story.append(Paragraph("法律咨询报告", self.styles['ChineseTitle']))
        story.append(Spacer(1, 10))

        # 基本信息表格
        info_data = [
            ['咨询编号', report.session_id],
            ['咨询时间', report.created_at.strftime('%Y年%m月%d日 %H:%M')],
            ['咨询领域', '、'.join(report.legal_domains)],
        ]
        info_table = Table(info_data, colWidths=[80, 400])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'SimSun'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 20))

        # 问题摘要
        story.append(Paragraph("一、问题摘要", self.styles['ChineseHeading']))
        story.append(Paragraph(report.summary, self.styles['ChineseBody']))

        # 核心问题
        story.append(Paragraph("二、核心法律问题", self.styles['ChineseHeading']))
        for i, issue in enumerate(report.key_issues, 1):
            story.append(Paragraph(f"{i}. {issue}", self.styles['ChineseBody']))

        # 法律分析
        story.append(Paragraph("三、法律分析", self.styles['ChineseHeading']))
        story.append(Paragraph(report.legal_analysis, self.styles['ChineseBody']))

        # 风险评估
        story.append(Paragraph("四、风险评估", self.styles['ChineseHeading']))
        risk_data = [['风险类型', '风险等级', '说明']]
        for risk in report.risk_assessment:
            risk_data.append([
                risk['category'],
                risk['level'],
                risk['description']
            ])
        risk_table = Table(risk_data, colWidths=[100, 80, 300])
        risk_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'SimSun'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a56db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(risk_table)
        story.append(Spacer(1, 15))

        # 建议
        story.append(Paragraph("五、行动建议", self.styles['ChineseHeading']))
        for i, rec in enumerate(report.recommendations, 1):
            story.append(Paragraph(f"{i}. {rec}", self.styles['ChineseBody']))

        # 法律依据
        story.append(Paragraph("六、法律依据", self.styles['ChineseHeading']))
        for law in report.referenced_laws:
            story.append(Paragraph(
                f"<b>《{law['name']}》第{law['article']}条</b>",
                self.styles['ChineseBody']
            ))
            story.append(Paragraph(
                law['content'],
                self.styles['ChineseSmall']
            ))
            story.append(Spacer(1, 5))

        # 免责声明
        story.append(Spacer(1, 30))
        story.append(Paragraph("免责声明", self.styles['ChineseHeading']))
        story.append(Paragraph(report.disclaimer, self.styles['ChineseSmall']))

        # 生成
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

class WordReportGenerator:
"""Word 报告生成器"""

    def generate(self, report: ConsultationReport) -> bytes:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        # 标题
        title = doc.add_heading('法律咨询报告', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 基本信息
        doc.add_paragraph(f"咨询编号：{report.session_id}")
        doc.add_paragraph(f"咨询时间：{report.created_at.strftime('%Y年%m月%d日 %H:%M')}")
        doc.add_paragraph(f"咨询领域：{'、'.join(report.legal_domains)}")

        # 各章节...
        doc.add_heading('一、问题摘要', level=1)
        doc.add_paragraph(report.summary)

        doc.add_heading('二、核心法律问题', level=1)
        for issue in report.key_issues:
            doc.add_paragraph(issue, style='List Bullet')

        doc.add_heading('三、法律分析', level=1)
        doc.add_paragraph(report.legal_analysis)

        doc.add_heading('四、风险评估', level=1)
        # 添加表格
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = '风险类型'
        hdr_cells[1].text = '风险等级'
        hdr_cells[2].text = '说明'
        for risk in report.risk_assessment:
            row_cells = table.add_row().cells
            row_cells[0].text = risk['category']
            row_cells[1].text = risk['level']
            row_cells[2].text = risk['description']

        doc.add_heading('五、行动建议', level=1)
        for rec in report.recommendations:
            doc.add_paragraph(rec, style='List Number')

        doc.add_heading('六、法律依据', level=1)
        for law in report.referenced_laws:
            p = doc.add_paragraph()
            p.add_run(f"《{law['name']}》第{law['article']}条").bold = True
            doc.add_paragraph(law['content'])

        # 免责声明
        doc.add_heading('免责声明', level=2)
        disclaimer_para = doc.add_paragraph(report.disclaimer)
        disclaimer_para.runs[0].font.size = Pt(9)
        disclaimer_para.runs[0].font.color.rgb = RGBColor(128, 128, 128)

        # 保存到 BytesIO
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

# API 端点

@router.get("/consultations/{session_id}/report")
async def generate_consultation_report(
session_id: str,
format: str = Query("pdf", regex="^(pdf|docx)$"),
current_user: User = Depends(get_current_user),
db: Session = Depends(get_db)
):
"""生成咨询报告""" # 获取咨询记录
consultation = await get_consultation_or_404(db, session_id, current_user)

    # 使用 LLM 分析对话并生成报告内容
    report_content = await analyze_and_generate_report(consultation)

    # 构建报告对象
    report = ConsultationReport(
        session_id=session_id,
        user_name=current_user.nickname or "用户",
        created_at=consultation.created_at,
        summary=report_content.summary,
        legal_domains=report_content.domains,
        key_issues=report_content.key_issues,
        legal_analysis=report_content.analysis,
        risk_assessment=report_content.risks,
        recommendations=report_content.recommendations,
        referenced_laws=report_content.laws,
        messages=[],  # 可选是否包含原始对话
        disclaimer=REPORT_DISCLAIMER
    )

    # 生成文件
    if format == "pdf":
        generator = PDFReportGenerator()
        content = generator.generate(report)
        media_type = "application/pdf"
        filename = f"法律咨询报告_{session_id}.pdf"
    else:
        generator = WordReportGenerator()
        content = generator.generate(report)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"法律咨询报告_{session_id}.docx"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

3.3 法律日历与提醒系统
Python

# backend/app/models/legal_calendar.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from app.database import Base
import enum

class ReminderType(enum.Enum):
STATUTE_OF_LIMITATIONS = "statute_of_limitations" # 诉讼时效
COURT_DATE = "court_date" # 开庭日期
DEADLINE = "deadline" # 截止日期
APPOINTMENT = "appointment" # 律师预约
CUSTOM = "custom" # 自定义

class LegalReminder(Base):
**tablename** = "legal_reminders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    consultation_id = Column(Integer, ForeignKey("consultations.id"), nullable=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    reminder_type = Column(Enum(ReminderType), nullable=False)

    due_date = Column(DateTime, nullable=False)
    remind_before_days = Column(Integer, default=7)  # 提前几天提醒

    is_completed = Column(Boolean, default=False)
    is_notified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# backend/app/services/reminder_service.py

class ReminderService:
"""提醒服务"""

    def __init__(self, db: Session):
        self.db = db

    async def create_from_consultation(
        self,
        consultation_id: int,
        user_id: int
    ) -> List[LegalReminder]:
        """根据咨询内容自动创建提醒"""
        consultation = await self.db.get(Consultation, consultation_id)

        # 使用 LLM 分析咨询内容，提取时间节点
        time_points = await self._extract_time_points(consultation)

        reminders = []
        for tp in time_points:
            reminder = LegalReminder(
                user_id=user_id,
                consultation_id=consultation_id,
                title=tp.title,
                description=tp.description,
                reminder_type=tp.type,
                due_date=tp.date,
                remind_before_days=tp.remind_before or 7
            )
            self.db.add(reminder)
            reminders.append(reminder)

        await self.db.commit()
        return reminders

    async def get_upcoming_reminders(
        self,
        user_id: int,
        days: int = 30
    ) -> List[LegalReminder]:
        """获取即将到来的提醒"""
        end_date = datetime.utcnow() + timedelta(days=days)

        result = await self.db.execute(
            select(LegalReminder)
            .where(
                LegalReminder.user_id == user_id,
                LegalReminder.is_completed == False,
                LegalReminder.due_date <= end_date
            )
            .order_by(LegalReminder.due_date)
        )
        return result.scalars().all()

    async def send_due_notifications(self):
        """发送到期提醒（定时任务调用）"""
        today = datetime.utcnow().date()

        # 查找需要提醒的事项
        reminders = await self.db.execute(
            select(LegalReminder)
            .where(
                LegalReminder.is_completed == False,
                LegalReminder.is_notified == False,
                func.date(LegalReminder.due_date) - LegalReminder.remind_before_days <= today
            )
        )

        for reminder in reminders.scalars():
            # 发送通知
            await notification_service.send(
                user_id=reminder.user_id,
                title=f"法律事项提醒：{reminder.title}",
                content=f"您有一个法律事项将于 {reminder.due_date.strftime('%Y年%m月%d日')} 到期",
                type="legal_reminder",
                data={"reminder_id": reminder.id}
            )

            reminder.is_notified = True

        await self.db.commit()

# API 端点

@router.post("/reminders")
async def create_reminder(
request: CreateReminderRequest,
current_user: User = Depends(get_current_user),
db: Session = Depends(get_db)
):
"""创建法律提醒"""
reminder = LegalReminder(
user_id=current_user.id,
\*\*request.model_dump()
)
db.add(reminder)
await db.commit()
return reminder

@router.get("/reminders")
async def get_reminders(
upcoming_days: int = Query(30, ge=1, le=365),
current_user: User = Depends(get_current_user),
db: Session = Depends(get_db)
):
"""获取提醒列表"""
service = ReminderService(db)
return await service.get_upcoming_reminders(current_user.id, upcoming_days)

@router.post("/consultations/{session_id}/auto-reminders")
async def create_auto_reminders(
session_id: str,
current_user: User = Depends(get_current_user),
db: Session = Depends(get_db)
):
"""根据咨询内容自动创建提醒"""
consultation = await get_consultation_or_404(db, session_id, current_user)

    service = ReminderService(db)
    reminders = await service.create_from_consultation(
        consultation.id,
        current_user.id
    )

    return {"created": len(reminders), "reminders": reminders}

TypeScript

// frontend/src/components/calendar/LegalCalendar.tsx

import { useState, useEffect } from 'react';
import { Calendar, Clock, Bell, Plus, Check, AlertTriangle } from 'lucide-react';
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay, isToday, isPast } from 'date-fns';
import { zhCN } from 'date-fns/locale';

interface LegalReminder {
id: number;
title: string;
description?: string;
reminderType: string;
dueDate: Date;
isCompleted: boolean;
consultationId?: number;
}

export const LegalCalendar: React.FC = () => {
const [currentMonth, setCurrentMonth] = useState(new Date());
const [reminders, setReminders] = useState<LegalReminder[]>([]);
const [selectedDate, setSelectedDate] = useState<Date | null>(null);
const [showAddModal, setShowAddModal] = useState(false);

useEffect(() => {
fetchReminders();
}, [currentMonth]);

const fetchReminders = async () => {
const response = await fetch('/api/ai/reminders?upcoming_days=60');
const data = await response.json();
setReminders(data.map((r: any) => ({
...r,
dueDate: new Date(r.due_date)
})));
};

const days = eachDayOfInterval({
start: startOfMonth(currentMonth),
end: endOfMonth(currentMonth)
});

const getRemindersForDate = (date: Date) => {
return reminders.filter(r => isSameDay(r.dueDate, date));
};

const toggleComplete = async (reminderId: number) => {
await fetch(`/api/ai/reminders/${reminderId}/toggle`, { method: 'POST' });
fetchReminders();
};

const reminderTypeLabels: Record<string, { label: string; color: string }> = {
statute_of_limitations: { label: '诉讼时效', color: 'bg-red-100 text-red-700' },
court_date: { label: '开庭日期', color: 'bg-purple-100 text-purple-700' },
deadline: { label: '截止日期', color: 'bg-orange-100 text-orange-700' },
appointment: { label: '律师预约', color: 'bg-blue-100 text-blue-700' },
custom: { label: '自定义', color: 'bg-gray-100 text-gray-700' },
};

return (

<div className="bg-white rounded-xl shadow-sm border">
{/_ 日历头部 _/}
<div className="flex items-center justify-between p-4 border-b">
<h2 className="text-lg font-semibold flex items-center gap-2">
<Calendar className="w-5 h-5 text-blue-600" />
法律日历
</h2>
<div className="flex items-center gap-2">
<button
onClick={() => setCurrentMonth(new Date(currentMonth.setMonth(currentMonth.getMonth() - 1)))}
className="p-2 hover:bg-gray-100 rounded" >
←
</button>
<span className="font-medium">
{format(currentMonth, 'yyyy 年 M 月', { locale: zhCN })}
</span>
<button
onClick={() => setCurrentMonth(new Date(currentMonth.setMonth(currentMonth.getMonth() + 1)))}
className="p-2 hover:bg-gray-100 rounded" >
→
</button>
</div>
<button
onClick={() => setShowAddModal(true)}
className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700" >
<Plus className="w-4 h-4" />
添加提醒
</button>
</div>

      {/* 日历网格 */}
      <div className="p-4">
        {/* 星期头 */}
        <div className="grid grid-cols-7 gap-1 mb-2">
          {['日', '一', '二', '三', '四', '五', '六'].map(day => (
            <div key={day} className="text-center text-sm text-gray-500 py-2">
              {day}
            </div>
          ))}
        </div>

        {/* 日期 */}
        <div className="grid grid-cols-7 gap-1">
          {days.map(day => {
            const dayReminders = getRemindersForDate(day);
            const hasReminders = dayReminders.length > 0;
            const hasUrgent = dayReminders.some(r =>
              !r.isCompleted && isPast(r.dueDate)
            );

            return (
              <button
                key={day.toISOString()}
                onClick={() => setSelectedDate(day)}
                className={`
                  relative p-2 min-h-[80px] rounded-lg text-left transition-colors
                  ${isToday(day) ? 'bg-blue-50 border-2 border-blue-200' : 'hover:bg-gray-50'}
                  ${isSameDay(day, selectedDate || new Date(0)) ? 'ring-2 ring-blue-500' : ''}
                `}
              >
                <span className={`text-sm ${isToday(day) ? 'font-bold text-blue-600' : ''}`}>
                  {format(day, 'd')}
                </span>

                {hasReminders && (
                  <div className="mt-1 space-y-1">
                    {dayReminders.slice(0, 2).map(r => (
                      <div
                        key={r.id}
                        className={`text-xs px-1 py-0.5 rounded truncate ${
                          r.isCompleted
                            ? 'bg-gray-100 text-gray-400 line-through'
                            : reminderTypeLabels[r.reminderType]?.color || 'bg-gray-100'
                        }`}
                      >
                        {r.title}
                      </div>
                    ))}
                    {dayReminders.length > 2 && (
                      <div className="text-xs text-gray-400">
                        +{dayReminders.length - 2} 更多
                      </div>
                    )}
                  </div>
                )}

                {hasUrgent && (
                  <AlertTriangle className="absolute top-1 right-1 w-4 h-4 text-red-500" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 选中日期的提醒列表 */}
      {selectedDate && (
        <div className="border-t p-4">
          <h3 className="font-medium mb-3">
            {format(selectedDate, 'M月d日 EEEE', { locale: zhCN })}的提醒
          </h3>

          {getRemindersForDate(selectedDate).length === 0 ? (
            <p className="text-gray-500 text-sm">暂无提醒事项</p>
          ) : (
            <div className="space-y-2">
              {getRemindersForDate(selectedDate).map(reminder => (
                <div
                  key={reminder.id}
                  className={`flex items-start gap-3 p-3 rounded-lg ${
                    reminder.isCompleted ? 'bg-gray-50' : 'bg-white border'
                  }`}
                >
                  <button
                    onClick={() => toggleComplete(reminder.id)}
                    className={`mt-0.5 w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                      reminder.isCompleted
                        ? 'bg-green-500 border-green-500 text-white'
                        : 'border-gray-300 hover:border-blue-500'
                    }`}
                  >
                    {reminder.isCompleted && <Check className="w-3 h-3" />}
                  </button>

                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`font-medium ${reminder.isCompleted ? 'line-through text-gray-400' : ''}`}>
                        {reminder.title}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        reminderTypeLabels[reminder.reminderType]?.color
                      }`}>
                        {reminderTypeLabels[reminder.reminderType]?.label}
                      </span>
                    </div>
                    {reminder.description && (
                      <p className="text-sm text-gray-500 mt-1">{reminder.description}</p>
                    )}
                    {reminder.consultationId && (
                      <a
                        href={`/chat?session=${reminder.consultationId}`}
                        className="text-xs text-blue-600 hover:underline mt-1 inline-block"
                      >
                        查看相关咨询 →
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>

);
};
3.4 智能快捷回复/常用语
Python

# backend/app/services/quick_replies.py

from typing import List
from pydantic import BaseModel

class QuickReply(BaseModel):
id: str
text: str
category: str
usage_count: int = 0

class QuickReplyService:
"""快捷回复服务"""

    # 系统预置快捷回复
    SYSTEM_REPLIES = {
        "开场": [
            "我遇到了一个法律问题想咨询一下",
            "请帮我分析一下这个情况",
            "我想了解一下相关的法律规定",
        ],
        "补充信息": [
            "这件事发生在{时间}",
            "涉及的金额大约是{金额}元",
            "我有{证据类型}作为证据",
            "对方是{关系}",
        ],
        "追问": [
            "这种情况的诉讼时效是多久？",
            "我需要准备什么证据？",
            "走法律程序大概需要多长时间？",
            "费用大概是多少？",
            "胜诉的可能性有多大？",
        ],
        "确认": [
            "我明白了，谢谢",
            "还有其他需要注意的吗？",
            "可以帮我推荐律师吗？",
        ],
    }

    def __init__(self, db: Session):
        self.db = db

    async def get_suggestions(
        self,
        user_id: int | None,
        context: str | None,
        intent: str | None
    ) -> List[QuickReply]:
        """获取快捷回复建议"""
        suggestions = []

        # 根据意图推荐
        if intent:
            category_map = {
                "greeting": "开场",
                "legal_consultation": "追问",
                "case_analysis": "补充信息",
            }
            category = category_map.get(intent, "追问")
            for text in self.SYSTEM_REPLIES.get(category, []):
                suggestions.append(QuickReply(
                    id=f"sys_{hash(text)}",
                    text=text,
                    category=category
                ))

        # 获取用户自定义快捷回复
        if user_id:
            user_replies = await self._get_user_replies(user_id)
            suggestions.extend(user_replies)

        # 根据上下文生成动态建议
        if context:
            dynamic = await self._generate_dynamic_suggestions(context)
            suggestions.extend(dynamic)

        return suggestions[:10]  # 最多返回10个

    async def _get_user_replies(self, user_id: int) -> List[QuickReply]:
        """获取用户自定义快捷回复"""
        result = await self.db.execute(
            select(UserQuickReply)
            .where(UserQuickReply.user_id == user_id)
            .order_by(UserQuickReply.usage_count.desc())
            .limit(5)
        )
        return [
            QuickReply(
                id=str(r.id),
                text=r.text,
                category="自定义",
                usage_count=r.usage_count
            )
            for r in result.scalars()
        ]

    async def _generate_dynamic_suggestions(self, context: str) -> List[QuickReply]:
        """基于上下文生成动态建议"""
        # 分析上下文中缺失的信息
        missing_info = await self._detect_missing_info(context)

        suggestions = []
        for info in missing_info[:3]:
            suggestions.append(QuickReply(
                id=f"dyn_{hash(info)}",
                text=info,
                category="补充"
            ))

        return suggestions

# API

@router.get("/quick-replies")
async def get_quick_replies(
context: str = Query(None),
intent: str = Query(None),
current_user: User | None = Depends(get_current_user_optional),
db: Session = Depends(get_db)
):
"""获取快捷回复建议"""
service = QuickReplyService(db)
return await service.get_suggestions(
user_id=current_user.id if current_user else None,
context=context,
intent=intent
)
TypeScript

// frontend/src/components/chat/QuickReplies.tsx

import { useState, useEffect } from 'react';
import { Zap, Plus, X, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface QuickReply {
id: string;
text: string;
category: string;
}

interface QuickRepliesProps {
onSelect: (text: string) => void;
context?: string;
intent?: string;
}

export const QuickReplies: React.FC<QuickRepliesProps> = ({
onSelect,
context,
intent,
}) => {
const [replies, setReplies] = useState<QuickReply[]>([]);
const [isExpanded, setIsExpanded] = useState(false);
const [activeCategory, setActiveCategory] = useState<string | null>(null);

useEffect(() => {
fetchReplies();
}, [context, intent]);

const fetchReplies = async () => {
const params = new URLSearchParams();
if (context) params.set('context', context);
if (intent) params.set('intent', intent);

    const response = await fetch(`/api/ai/quick-replies?${params}`);
    const data = await response.json();
    setReplies(data);

};

// 按类别分组
const categories = replies.reduce((acc, reply) => {
if (!acc[reply.category]) {
acc[reply.category] = [];
}
acc[reply.category].push(reply);
return acc;
}, {} as Record<string, QuickReply[]>);

return (

<div className="relative">
{/_ 折叠状态显示快捷按钮 _/}
{!isExpanded && (
<div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
<button
onClick={() => setIsExpanded(true)}
className="flex-shrink-0 flex items-center gap-1 px-3 py-1.5 bg-blue-50 text-blue-600 rounded-full text-sm hover:bg-blue-100" >
<Zap className="w-4 h-4" />
快捷回复
</button>

          {replies.slice(0, 4).map((reply) => (
            <button
              key={reply.id}
              onClick={() => onSelect(reply.text)}
              className="flex-shrink-0 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-sm whitespace-nowrap"
            >
              {reply.text.length > 15 ? reply.text.slice(0, 15) + '...' : reply.text}
            </button>
          ))}

          {replies.length > 4 && (
            <button
              onClick={() => setIsExpanded(true)}
              className="flex-shrink-0 px-2 py-1.5 text-gray-500 hover:text-gray-700 text-sm"
            >
              +{replies.length - 4}
            </button>
          )}
        </div>
      )}

      {/* 展开状态 */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="absolute bottom-full left-0 right-0 mb-2 bg-white rounded-xl shadow-lg border p-4 z-10"
          >
            {/* 头部 */}
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium flex items-center gap-2">
                <Zap className="w-4 h-4 text-blue-600" />
                快捷回复
              </h3>
              <button
                onClick={() => setIsExpanded(false)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* 类别标签 */}
            <div className="flex gap-2 mb-3 overflow-x-auto">
              {Object.keys(categories).map((category) => (
                <button
                  key={category}
                  onClick={() => setActiveCategory(
                    activeCategory === category ? null : category
                  )}
                  className={`px-3 py-1 rounded-full text-sm whitespace-nowrap ${
                    activeCategory === category
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 hover:bg-gray-200'
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>

            {/* 回复列表 */}
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {Object.entries(categories)
                .filter(([cat]) => !activeCategory || cat === activeCategory)
                .map(([category, items]) => (
                  <div key={category}>
                    {!activeCategory && (
                      <p className="text-xs text-gray-500 mb-1">{category}</p>
                    )}
                    <div className="flex flex-wrap gap-2">
                      {items.map((reply) => (
                        <button
                          key={reply.id}
                          onClick={() => {
                            onSelect(reply.text);
                            setIsExpanded(false);
                          }}
                          className="px-3 py-1.5 bg-gray-50 hover:bg-gray-100 rounded-lg text-sm text-left transition-colors"
                        >
                          {reply.text}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
            </div>

            {/* 自定义快捷回复入口 */}
            <button className="mt-3 flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700">
              <Plus className="w-4 h-4" />
              添加自定义快捷回复
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>

);
};
3.5 对话分享与协作
Python

# backend/app/models/shared_consultation.py

class SharedConsultation(Base):
**tablename** = "shared_consultations"

    id = Column(Integer, primary_key=True)
    consultation_id = Column(Integer, ForeignKey("consultations.id"))
    share_code = Column(String(32), unique=True, index=True)

    shared_by_user_id = Column(Integer, ForeignKey("users.id"))

    # 分享设置
    expires_at = Column(DateTime, nullable=True)  # 过期时间
    password = Column(String(100), nullable=True)  # 访问密码（加密）
    allow_comments = Column(Boolean, default=False)  # 允许评论
    is_anonymous = Column(Boolean, default=True)  # 匿名分享

    view_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

class ConsultationComment(Base):
**tablename** = "consultation_comments"

    id = Column(Integer, primary_key=True)
    shared_consultation_id = Column(Integer, ForeignKey("shared_consultations.id"))

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    guest_name = Column(String(50), nullable=True)

    content = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey("consultation_comments.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

# API

@router.post("/consultations/{session_id}/share")
async def share_consultation(
session_id: str,
request: ShareConsultationRequest,
current_user: User = Depends(get_current_user),
db: Session = Depends(get_db)
):
"""分享咨询记录"""
consultation = await get_consultation_or_404(db, session_id, current_user)

    # 生成分享码
    share_code = secrets.token_urlsafe(16)

    # 处理密码
    hashed_password = None
    if request.password:
        hashed_password = hash_password(request.password)

    shared = SharedConsultation(
        consultation_id=consultation.id,
        share_code=share_code,
        shared_by_user_id=current_user.id,
        expires_at=request.expires_at,
        password=hashed_password,
        allow_comments=request.allow_comments,
        is_anonymous=request.is_anonymous
    )

    db.add(shared)
    await db.commit()

    share_url = f"{settings.frontend_url}/shared/{share_code}"

    return {
        "share_code": share_code,
        "share_url": share_url,
        "expires_at": request.expires_at
    }

@router.get("/shared/{share_code}")
async def get_shared_consultation(
share_code: str,
password: str = Query(None),
db: Session = Depends(get_db)
):
"""获取分享的咨询记录"""
shared = await db.execute(
select(SharedConsultation)
.where(SharedConsultation.share_code == share_code)
)
shared = shared.scalar_one_or_none()

    if not shared:
        raise HTTPException(404, "分享不存在或已过期")

    # 检查过期
    if shared.expires_at and shared.expires_at < datetime.utcnow():
        raise HTTPException(410, "分享已过期")

    # 检查密码
    if shared.password:
        if not password or not verify_password(password, shared.password):
            raise HTTPException(401, "需要密码访问")

    # 更新访问计数
    shared.view_count += 1
    await db.commit()

    # 获取咨询内容
    consultation = await db.get(Consultation, shared.consultation_id)

    # 脱敏处理（如果是匿名分享）
    messages = consultation.messages
    if shared.is_anonymous:
        messages = anonymize_messages(messages)

    return {
        "messages": messages,
        "created_at": consultation.created_at,
        "allow_comments": shared.allow_comments,
        "view_count": shared.view_count
    }

@router.post("/shared/{share_code}/comments")
async def add_comment(
share_code: str,
request: AddCommentRequest,
current_user: User | None = Depends(get_current_user_optional),
db: Session = Depends(get_db)
):
"""添加评论"""
shared = await get_shared_or_404(db, share_code)

    if not shared.allow_comments:
        raise HTTPException(403, "此分享不允许评论")

    comment = ConsultationComment(
        shared_consultation_id=shared.id,
        user_id=current_user.id if current_user else None,
        guest_name=request.guest_name if not current_user else None,
        content=request.content,
        parent_id=request.parent_id
    )

    db.add(comment)
    await db.commit()

    return comment

四、进阶功能扩展
4.1 用户画像与个性化推荐
Python

# backend/app/services/user_profile.py

from dataclasses import dataclass
from typing import List, Optional
from collections import Counter

@dataclass
class UserLegalProfile:
user_id: int

    # 咨询统计
    total_consultations: int
    total_messages: int
    avg_session_length: float

    # 关注领域
    primary_domains: List[str]  # 主要关注的法律领域
    domain_distribution: dict   # 领域分布

    # 问题特征
    common_topics: List[str]    # 常见话题
    question_complexity: str    # 问题复杂度：simple/medium/complex

    # 行为特征
    preferred_time: str         # 偏好咨询时间
    avg_rating_given: float     # 平均给出的评分

    # 个性化设置推荐
    recommended_features: List[str]

class UserProfileService:
"""用户画像服务"""

    def __init__(self, db: Session):
        self.db = db

    async def build_profile(self, user_id: int) -> UserLegalProfile:
        """构建用户画像"""
        # 获取用户咨询历史
        consultations = await self._get_user_consultations(user_id)

        if not consultations:
            return self._default_profile(user_id)

        # 分析咨询领域
        domains = await self._analyze_domains(consultations)

        # 分析问题特征
        topics = await self._analyze_topics(consultations)
        complexity = await self._analyze_complexity(consultations)

        # 分析行为模式
        behavior = await self._analyze_behavior(user_id, consultations)

        # 生成个性化推荐
        recommendations = self._generate_recommendations(
            domains, topics, complexity
        )

        return UserLegalProfile(
            user_id=user_id,
            total_consultations=len(consultations),
            total_messages=sum(len(c.messages) for c in consultations),
            avg_session_length=behavior['avg_session_length'],
            primary_domains=domains['primary'],
            domain_distribution=domains['distribution'],
            common_topics=topics,
            question_complexity=complexity,
            preferred_time=behavior['preferred_time'],
            avg_rating_given=behavior['avg_rating'],
            recommended_features=recommendations
        )

    async def get_personalized_suggestions(
        self,
        user_id: int,
        current_context: str = None
    ) -> dict:
        """获取个性化建议"""
        profile = await self.build_profile(user_id)

        suggestions = {
            "greeting": self._get_personalized_greeting(profile),
            "quick_questions": self._get_personalized_questions(profile),
            "related_articles": await self._get_related_articles(profile),
            "lawyer_recommendations": await self._get_lawyer_recommendations(profile),
        }

        return suggestions

    def _get_personalized_greeting(self, profile: UserLegalProfile) -> str:
        """个性化问候语"""
        if profile.total_consultations == 0:
            return "您好！我是您的法律咨询助手，有什么可以帮您的？"

        domain = profile.primary_domains[0] if profile.primary_domains else "法律"

        greetings = [
            f"您好！看到您之前咨询过{domain}相关问题，今天有什么需要帮助的吗？",
            f"欢迎回来！有新的法律问题需要咨询吗？",
            f"您好！根据您的咨询记录，为您准备了一些{domain}领域的最新资讯。",
        ]

        import random
        return random.choice(greetings)

    def _get_personalized_questions(self, profile: UserLegalProfile) -> List[str]:
        """个性化问题建议"""
        questions = []

        for domain in profile.primary_domains[:2]:
            domain_questions = {
                "劳动纠纷": [
                    "最近的劳动法有什么新规定？",
                    "我想了解试用期的相关规定",
                ],
                "合同纠纷": [
                    "电子合同有法律效力吗？",
                    "合同违约金一般是多少？",
                ],
                "婚姻家庭": [
                    "婚前财产协议怎么写？",
                    "离婚后房产如何分割？",
                ],
            }
            questions.extend(domain_questions.get(domain, []))

        return questions[:5]

# API

@router.get("/profile")
async def get_user_profile(
current_user: User = Depends(get_current_user),
db: Session = Depends(get_db)
):
"""获取用户画像"""
service = UserProfileService(db)
return await service.build_profile(current_user.id)

@router.get("/personalized-suggestions")
async def get_personalized_suggestions(
context: str = Query(None),
current_user: User = Depends(get_current_user),
db: Session = Depends(get_db)
):
"""获取个性化建议"""
service = UserProfileService(db)
return await service.get_personalized_suggestions(
current_user.id,
context
)
4.2 离线支持 (PWA)
TypeScript

// frontend/src/service-worker.ts

/// <reference lib="webworker" />

declare const self: ServiceWorkerGlobalScope;

const CACHE_NAME = 'legal-assistant-v1';
const OFFLINE_URL = '/offline.html';

// 需要缓存的资源
const STATIC_ASSETS = [
'/',
'/offline.html',
'/manifest.json',
'/icons/icon-192.png',
'/icons/icon-512.png',
];

// 安装事件
self.addEventListener('install', (event) => {
event.waitUntil(
caches.open(CACHE_NAME).then((cache) => {
return cache.addAll(STATIC_ASSETS);
})
);
self.skipWaiting();
});

// 激活事件
self.addEventListener('activate', (event) => {
event.waitUntil(
caches.keys().then((cacheNames) => {
return Promise.all(
cacheNames
.filter((name) => name !== CACHE_NAME)
.map((name) => caches.delete(name))
);
})
);
self.clients.claim();
});

// 请求拦截
self.addEventListener('fetch', (event) => {
const { request } = event;
const url = new URL(request.url);

// API 请求：网络优先，失败时返回缓存
if (url.pathname.startsWith('/api/')) {
event.respondWith(
fetch(request)
.then((response) => {
// 缓存成功的 GET 请求
if (request.method === 'GET' && response.ok) {
const responseClone = response.clone();
caches.open(CACHE_NAME).then((cache) => {
cache.put(request, responseClone);
});
}
return response;
})
.catch(async () => {
const cachedResponse = await caches.match(request);
if (cachedResponse) {
return cachedResponse;
}
// 返回离线提示
return new Response(
JSON.stringify({ error: 'offline', message: '您当前处于离线状态' }),
{ headers: { 'Content-Type': 'application/json' } }
);
})
);
return;
}

// 静态资源：缓存优先
event.respondWith(
caches.match(request).then((cachedResponse) => {
if (cachedResponse) {
return cachedResponse;
}
return fetch(request).then((response) => {
if (response.ok) {
const responseClone = response.clone();
caches.open(CACHE_NAME).then((cache) => {
cache.put(request, responseClone);
});
}
return response;
});
}).catch(() => {
// 页面请求失败时返回离线页
if (request.mode === 'navigate') {
return caches.match(OFFLINE_URL);
}
return new Response('Offline', { status: 503 });
})
);
});

// 后台同步
self.addEventListener('sync', (event) => {
if (event.tag === 'sync-messages') {
event.waitUntil(syncPendingMessages());
}
});

async function syncPendingMessages() {
// 从 IndexedDB 获取待发送消息
const pendingMessages = await getPendingMessages();

for (const msg of pendingMessages) {
try {
await fetch('/api/ai/chat', {
method: 'POST',
headers: { 'Content-Type': 'application/json' },
body: JSON.stringify(msg),
});
await removePendingMessage(msg.id);
} catch (error) {
console.error('Failed to sync message:', error);
}
}
}
TypeScript

// frontend/src/hooks/useOfflineSupport.ts

import { useState, useEffect, useCallback } from 'react';
import { openDB, DBSchema, IDBPDatabase } from 'idb';

interface PendingMessage {
id: string;
sessionId: string;
message: string;
timestamp: number;
}

interface LegalAssistantDB extends DBSchema {
pendingMessages: {
key: string;
value: PendingMessage;
};
cachedResponses: {
key: string;
value: {
question: string;
answer: string;
references: any[];
timestamp: number;
};
};
}

export const useOfflineSupport = () => {
const [isOnline, setIsOnline] = useState(navigator.onLine);
const [db, setDb] = useState<IDBPDatabase<LegalAssistantDB> | null>(null);
const [pendingCount, setPendingCount] = useState(0);

// 初始化数据库
useEffect(() => {
const initDB = async () => {
const database = await openDB<LegalAssistantDB>('legal-assistant', 1, {
upgrade(db) {
db.createObjectStore('pendingMessages', { keyPath: 'id' });
db.createObjectStore('cachedResponses', { keyPath: 'question' });
},
});
setDb(database);
updatePendingCount(database);
};

    initDB();

}, []);

// 监听网络状态
useEffect(() => {
const handleOnline = () => {
setIsOnline(true);
// 触发后台同步
if ('serviceWorker' in navigator && 'sync' in ServiceWorkerRegistration.prototype) {
navigator.serviceWorker.ready.then((registration) => {
(registration as any).sync.register('sync-messages');
});
}
};

    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };

}, []);

const updatePendingCount = async (database: IDBPDatabase<LegalAssistantDB>) => {
const count = await database.count('pendingMessages');
setPendingCount(count);
};

// 保存待发送消息
const savePendingMessage = useCallback(async (sessionId: string, message: string) => {
if (!db) return;

    const pendingMessage: PendingMessage = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      sessionId,
      message,
      timestamp: Date.now(),
    };

    await db.put('pendingMessages', pendingMessage);
    updatePendingCount(db);

    return pendingMessage.id;

}, [db]);

// 获取缓存的回复
const getCachedResponse = useCallback(async (question: string) => {
if (!db) return null;

    // 简单的模糊匹配
    const allCached = await db.getAll('cachedResponses');
    const matched = allCached.find((cached) =>
      cached.question.includes(question) || question.includes(cached.question)
    );

    if (matched && Date.now() - matched.timestamp < 7 * 24 * 60 * 60 * 1000) {
      return matched;
    }

    return null;

}, [db]);

// 缓存回复
const cacheResponse = useCallback(async (
question: string,
answer: string,
references: any[]
) => {
if (!db) return;

    await db.put('cachedResponses', {
      question,
      answer,
      references,
      timestamp: Date.now(),
    });

}, [db]);

return {
isOnline,
pendingCount,
savePendingMessage,
getCachedResponse,
cacheResponse,
};
};
4.3 多语言支持（扩展）
TypeScript

// frontend/src/i18n/legal-terms.ts

// 法律术语多语言映射
export const legalTerms = {
zh: {
// 法律领域
domains: {
civil: '民事',
criminal: '刑事',
administrative: '行政',
labor: '劳动',
commercial: '商事',
intellectual_property: '知识产权',
family: '婚姻家庭',
},
// 常见法律术语
terms: {
plaintiff: '原告',
defendant: '被告',
lawsuit: '诉讼',
judgment: '判决',
evidence: '证据',
statute_of_limitations: '诉讼时效',
contract: '合同',
tort: '侵权',
damages: '损害赔偿',
mediation: '调解',
arbitration: '仲裁',
},
// 法律文书
documents: {
complaint: '起诉状',
answer: '答辩状',
motion: '申请书',
contract: '合同',
power_of_attorney: '委托书',
},
},
en: {
domains: {
civil: 'Civil Law',
criminal: 'Criminal Law',
administrative: 'Administrative Law',
labor: 'Labor Law',
commercial: 'Commercial Law',
intellectual_property: 'Intellectual Property',
family: 'Family Law',
},
terms: {
plaintiff: 'Plaintiff',
defendant: 'Defendant',
lawsuit: 'Lawsuit',
judgment: 'Judgment',
evidence: 'Evidence',
statute_of_limitations: 'Statute of Limitations',
contract: 'Contract',
tort: 'Tort',
damages: 'Damages',
mediation: 'Mediation',
arbitration: 'Arbitration',
},
documents: {
complaint: 'Complaint',
answer: 'Answer',
motion: 'Motion',
contract: 'Contract',
power_of_attorney: 'Power of Attorney',
},
},
};

// 法律术语解释弹窗
export const termDefinitions = {
zh: {
statute_of_limitations: {
term: '诉讼时效',
definition: '权利人向人民法院请求保护民事权利的法定期间。超过诉讼时效期间的，权利人丧失胜诉权。',
example: '一般民事诉讼时效为 3 年，自权利人知道或者应当知道权利受到损害之日起计算。',
},
// ... 更多术语
},
};
4.4 无障碍功能
TypeScript

// frontend/src/components/accessibility/AccessibilityProvider.tsx

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface AccessibilitySettings {
fontSize: 'normal' | 'large' | 'x-large';
highContrast: boolean;
reducedMotion: boolean;
screenReaderOptimized: boolean;
keyboardNavigation: boolean;
}

interface AccessibilityContextType {
settings: AccessibilitySettings;
updateSettings: (updates: Partial<AccessibilitySettings>) => void;
announce: (message: string, priority?: 'polite' | 'assertive') => void;
}

const AccessibilityContext = createContext<AccessibilityContextType | null>(null);

export const AccessibilityProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
const [settings, setSettings] = useState<AccessibilitySettings>(() => {
const saved = localStorage.getItem('accessibility-settings');
return saved ? JSON.parse(saved) : {
fontSize: 'normal',
highContrast: false,
reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
screenReaderOptimized: false,
keyboardNavigation: false,
};
});

// 应用设置到 DOM
useEffect(() => {
const root = document.documentElement;

    // 字体大小
    const fontSizeMap = { normal: '16px', large: '18px', 'x-large': '20px' };
    root.style.fontSize = fontSizeMap[settings.fontSize];

    // 高对比度
    root.classList.toggle('high-contrast', settings.highContrast);

    // 减少动画
    root.classList.toggle('reduced-motion', settings.reducedMotion);

    // 保存设置
    localStorage.setItem('accessibility-settings', JSON.stringify(settings));

}, [settings]);

const updateSettings = (updates: Partial<AccessibilitySettings>) => {
setSettings(prev => ({ ...prev, ...updates }));
};

// 屏幕阅读器公告
const announce = (message: string, priority: 'polite' | 'assertive' = 'polite') => {
const announcer = document.getElementById('sr-announcer') || createAnnouncer();
announcer.setAttribute('aria-live', priority);
announcer.textContent = message;

    // 清空以便下次公告
    setTimeout(() => {
      announcer.textContent = '';
    }, 1000);

};

const createAnnouncer = () => {
const announcer = document.createElement('div');
announcer.id = 'sr-announcer';
announcer.setAttribute('aria-live', 'polite');
announcer.setAttribute('aria-atomic', 'true');
announcer.className = 'sr-only';
document.body.appendChild(announcer);
return announcer;
};

return (
<AccessibilityContext.Provider value={{ settings, updateSettings, announce }}>
{children}
{/_ 跳过导航链接 _/}
<a 
        href="#main-content" 
        className="sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 focus:z-50 focus:p-4 focus:bg-blue-600 focus:text-white"
      >
跳到主要内容
</a>
</AccessibilityContext.Provider>
);
};

export const useAccessibility = () => {
const context = useContext(AccessibilityContext);
if (!context) {
throw new Error('useAccessibility must be used within AccessibilityProvider');
}
return context;
};

// 无障碍聊天消息组件
export const AccessibleChatMessage: React.FC<{
role: 'user' | 'assistant';
content: string;
references?: any[];
timestamp: Date;
}> = ({ role, content, references, timestamp }) => {
const { settings, announce } = useAccessibility();

useEffect(() => {
if (role === 'assistant' && settings.screenReaderOptimized) {
announce(`AI助手回复：${content.slice(0, 100)}...`);
}
}, [content]);

return (

<article
role="article"
aria-label={`${role === 'user' ? '您' : 'AI助手'}的消息`}
className={`chat-message ${role}`} >
<header className="sr-only">
<span>{role === 'user' ? '您' : 'AI 助手'}</span>
<time dateTime={timestamp.toISOString()}>
{timestamp.toLocaleTimeString()}
</time>
</header>

      <div
        className="message-content"
        // 使内容可被屏幕阅读器朗读
        tabIndex={0}
        role="text"
      >
        {content}
      </div>

      {references && references.length > 0 && (
        <aside aria-label="法律参考">
          <h4 className="sr-only">相关法条</h4>
          <ul>
            {references.map((ref, i) => (
              <li key={i}>
                <span className="sr-only">引用：</span>
                《{ref.lawName}》第{ref.articleNumber}条
              </li>
            ))}
          </ul>
        </aside>
      )}
    </article>

);
};
五、功能完整性检查清单
5.1 核心功能完善
功能 状态 优先级 说明
语音输入 已完成 🟡 中 提升移动端体验
文件上传分析 已完成 🟡 中 合同/证据智能分析
咨询报告导出 已完成 🟡 中 PDF/Word 格式
法律日历提醒 已完成 🟡 中 诉讼时效等提醒
律师转接 已完成 🔴 高 AI 转人工服务
对话分享 已完成 🟢 低 匿名分享咨询
5.2 体验优化
功能 状态 优先级 说明
法条弹窗高亮 已完成 🔴 高 点击法条显示详情
AI 思考过程展示 部分完成 🟡 中 透明化 AI 推理
快捷回复 已完成 🟡 中 常用语快速输入
对话搜索 已完成 🟡 中 历史记录搜索
诉讼时效计算器 已完成 🟡 中 实用工具
费用估算器 已完成 🟡 中 实用工具
5.3 技术增强
功能 状态 优先级 说明
多模型支持 已完成 🟡 中 模型降级与切换
离线支持(PWA) 已完成 🟢 低 离线缓存
FAQ 自动生成 已完成 🟢 低 基于历史对话
知识库管理 已完成 🟡 中 后台管理界面
对话质量分析 已完成 🟡 中 仪表板数据
六、完整实施路线图（修订版）
第一阶段（2-3 周）- 核心体验
text

Week 1:

- [x] 法条弹窗高亮组件
- [x] 消息操作工具栏（复制/收藏/评价）
- [x] 快捷回复系统（前后端）

Week 2:

- [x] 诉讼时效计算器
- [x] 费用估算器
- [x] 对话历史搜索

Week 3:

- [x] 咨询报告导出（PDF）
- [ ] AI 思考过程展示
      第二阶段（2-3 周）- 功能扩展
      text

Week 4:

- [x] 语音输入（前端 + 后端 Whisper）
- [x] 文件上传与分析

Week 5:

- [x] 法律日历与提醒系统
- [x] 律师转接功能基础版

Week 6:

- [x] 用户画像与个性化
- [x] 多模型支持与 Fallback
      第三阶段（2 周）- 运营工具
      text

Week 7:

- [x] FAQ 自动生成
- [x] 知识库管理后台
- [x] 对话质量分析仪表板

Week 8:

- [x] 对话分享功能
- [x] 无障碍功能完善
- [x] PWA 离线支持
