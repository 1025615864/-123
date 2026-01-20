from __future__ import annotations

from app.services.content_safety import ContentSafetyFilter, RiskLevel


def test_content_safety_blocked_pattern() -> None:
    f = ContentSafetyFilter()
    r = f.check_input("如何杀人")
    assert r.risk_level == RiskLevel.BLOCKED
    assert r.should_log is True
    assert r.suggestion
    assert r.triggered_rules and r.triggered_rules[0].startswith("blocked:")


def test_content_safety_high_risk_keyword() -> None:
    f = ContentSafetyFilter()
    r = f.check_input("我想自杀")
    assert r.risk_level == RiskLevel.HIGH
    assert r.should_log is True
    assert any(x.startswith("high_risk:") for x in r.triggered_rules)


def test_content_safety_sensitive_topic() -> None:
    f = ContentSafetyFilter()
    r = f.check_input("政府腐败怎么办")
    assert r.risk_level == RiskLevel.MEDIUM
    assert r.should_log is True
    assert r.suggestion is None
    assert "sensitive:政治敏感" in r.triggered_rules


def test_content_safety_safe() -> None:
    f = ContentSafetyFilter()
    r = f.check_input("你好")
    assert r.risk_level == RiskLevel.SAFE
    assert r.triggered_rules == []


def test_content_safety_sanitize_output() -> None:
    f = ContentSafetyFilter()
    text = "电话13800138000 身份证11010519491231002X"
    out = f.sanitize_output(text)
    assert "[电话号码已隐藏]" in out
    assert "[身份证号已隐藏]" not in out

    text2 = "身份证110105194912310020"
    out2 = f.sanitize_output(text2)
    assert "[身份证号已隐藏]" in out2
