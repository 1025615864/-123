from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .content_safety import RiskLevel


@dataclass(frozen=True)
class SearchQuality:
    total_candidates: int
    qualified_count: int
    avg_similarity: float
    confidence: str


class ResponseStrategy(str, Enum):
    FULL_RAG = "full_rag"
    PARTIAL_RAG = "partial_rag"
    GENERAL_LEGAL = "general_legal"
    REFUSE_ANSWER = "refuse"
    REDIRECT = "redirect"


@dataclass(frozen=True)
class StrategyDecision:
    strategy: ResponseStrategy
    reason: str
    confidence: str


class ResponseStrategyDecider:
    HIGH_RISK_KEYWORDS: list[str] = [
        "刑事",
        "犯罪",
        "判刑",
        "坐牢",
        "死刑",
        "伪造",
        "诈骗",
    ]

    COMPLEX_PATTERNS: list[str] = [
        r"涉及.*金额.*万",
        r"多方.*纠纷",
        r"跨.*境",
    ]

    def decide(self, query: str, search_quality: SearchQuality, *, risk_level: RiskLevel) -> StrategyDecision:
        q = str(query or "")

        if risk_level == RiskLevel.BLOCKED:
            return StrategyDecision(
                strategy=ResponseStrategy.REFUSE_ANSWER,
                reason="内容安全拦截",
                confidence="N/A",
            )

        if self._contains_high_risk(q):
            return StrategyDecision(
                strategy=ResponseStrategy.REDIRECT,
                reason="涉及刑事或高风险法律问题",
                confidence="N/A",
            )

        if self._is_complex(q):
            return StrategyDecision(
                strategy=ResponseStrategy.PARTIAL_RAG,
                reason="问题较为复杂",
                confidence=str(search_quality.confidence),
            )

        conf = str(search_quality.confidence)
        if conf == "high":
            return StrategyDecision(
                strategy=ResponseStrategy.FULL_RAG,
                reason="找到高相关法律依据",
                confidence="high",
            )
        if conf == "medium":
            return StrategyDecision(
                strategy=ResponseStrategy.PARTIAL_RAG,
                reason="找到部分相关法律依据",
                confidence="medium",
            )

        return StrategyDecision(
            strategy=ResponseStrategy.GENERAL_LEGAL,
            reason="未找到直接相关法条",
            confidence="low",
        )

    def _contains_high_risk(self, text: str) -> bool:
        for kw in self.HIGH_RISK_KEYWORDS:
            if kw in text:
                return True
        return False

    def _is_complex(self, text: str) -> bool:
        for pattern in self.COMPLEX_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
