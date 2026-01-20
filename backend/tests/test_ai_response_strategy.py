from __future__ import annotations

from app.services.ai_response_strategy import (
    ResponseStrategy,
    ResponseStrategyDecider,
    SearchQuality,
)
from app.services.content_safety import RiskLevel


def _sq(conf: str) -> SearchQuality:
    return SearchQuality(total_candidates=10, qualified_count=3, avg_similarity=0.7, confidence=conf)


def test_strategy_blocked_refuse() -> None:
    d = ResponseStrategyDecider()
    out = d.decide("任何问题", _sq("high"), risk_level=RiskLevel.BLOCKED)
    assert out.strategy == ResponseStrategy.REFUSE_ANSWER
    assert out.confidence == "N/A"


def test_strategy_high_risk_redirect() -> None:
    d = ResponseStrategyDecider()
    out = d.decide("涉嫌诈骗怎么办", _sq("high"), risk_level=RiskLevel.LOW)
    assert out.strategy == ResponseStrategy.REDIRECT


def test_strategy_complex_partial_rag() -> None:
    d = ResponseStrategyDecider()
    out = d.decide("涉及金额10万的纠纷", _sq("medium"), risk_level=RiskLevel.SAFE)
    assert out.strategy == ResponseStrategy.PARTIAL_RAG
    assert out.confidence == "medium"


def test_strategy_confidence_high_full_rag() -> None:
    d = ResponseStrategyDecider()
    out = d.decide("一般问题", _sq("high"), risk_level=RiskLevel.SAFE)
    assert out.strategy == ResponseStrategy.FULL_RAG


def test_strategy_confidence_medium_partial_rag() -> None:
    d = ResponseStrategyDecider()
    out = d.decide("一般问题", _sq("medium"), risk_level=RiskLevel.SAFE)
    assert out.strategy == ResponseStrategy.PARTIAL_RAG


def test_strategy_confidence_low_general_legal() -> None:
    d = ResponseStrategyDecider()
    out = d.decide("一般问题", _sq("low"), risk_level=RiskLevel.SAFE)
    assert out.strategy == ResponseStrategy.GENERAL_LEGAL


def test_helpers() -> None:
    d = ResponseStrategyDecider()
    assert d._contains_high_risk("诈骗") is True
    assert d._contains_high_risk("无") is False
    assert d._is_complex("跨境纠纷") is True
    assert d._is_complex("简单") is False
