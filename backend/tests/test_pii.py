import re

import pytest

import app.utils.pii as pii
from app.utils.pii import sanitize_pii


def test_sanitize_pii_masks_common_patterns():
    text = "手机号：13800138000 身份证：11010519900101123X 邮箱 test@example.com 银行卡 6222020402040204020"
    out = sanitize_pii(text)
    assert "13800138000" not in out
    assert "11010519900101123X" not in out
    assert "test@example.com" not in out
    assert "6222020402040204020" not in out
    assert "【手机号已脱敏】" in out
    assert "【身份证号已脱敏】" in out
    assert "【邮箱已脱敏】" in out
    assert "【银行卡号已脱敏】" in out


def test_sanitize_pii_empty_returns_empty():
    assert sanitize_pii("") == ""


def test_sanitize_pii_bank_repl_keeps_11_digits_non_phone_and_15_18_when_id_regex_disabled(monkeypatch: pytest.MonkeyPatch):
    out = sanitize_pii("11000000000")
    assert out == "11000000000"

    monkeypatch.setattr(pii, "_ID18_RE", re.compile(r"a^"), raising=True)
    monkeypatch.setattr(pii, "_ID15_RE", re.compile(r"a^"), raising=True)

    d18 = "123456789012345678"
    assert sanitize_pii(d18) == d18

    d15 = "123456789012345"
    assert sanitize_pii(d15) == d15
