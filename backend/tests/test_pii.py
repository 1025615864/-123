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
