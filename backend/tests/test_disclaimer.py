from __future__ import annotations

from app.services.ai_response_strategy import ResponseStrategy
from app.services.content_safety import RiskLevel
from app.services.disclaimer import DisclaimerManager


def test_disclaimer_general_when_no_risk_and_not_redirect() -> None:
    mgr = DisclaimerManager()
    out = mgr.get_disclaimer(risk_level=RiskLevel.SAFE, strategy=ResponseStrategy.GENERAL_LEGAL)
    assert out == mgr.GENERAL_DISCLAIMER


def test_disclaimer_high_risk() -> None:
    mgr = DisclaimerManager()
    out = mgr.get_disclaimer(risk_level=RiskLevel.HIGH, strategy=ResponseStrategy.GENERAL_LEGAL)
    assert "高风险提示" in out
    assert "正式法律意见" not in out


def test_disclaimer_medium_risk_and_redirect() -> None:
    mgr = DisclaimerManager()
    out = mgr.get_disclaimer(risk_level=RiskLevel.MEDIUM, strategy=ResponseStrategy.REDIRECT)
    assert "风险提示" in out
    assert "预约专业律师咨询" in out
    assert "重要提示" not in out


def test_disclaimer_redirect_without_risk_uses_redirect_text_only() -> None:
    mgr = DisclaimerManager()
    out = mgr.get_disclaimer(risk_level=RiskLevel.SAFE, strategy=ResponseStrategy.REDIRECT)
    assert "预约专业律师咨询" in out
    assert "重要提示" not in out
