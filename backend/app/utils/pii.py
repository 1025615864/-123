from __future__ import annotations

import re


_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_ID18_RE = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")
_ID15_RE = re.compile(r"(?<!\d)(\d{15})(?!\d)")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _mask_labeled(text: str, *, label: str, replacement: str) -> str:
    # Replace content after a label within a single line.
    # Example: "身份证：110..." -> "身份证：【身份证号已脱敏】"
    pat = re.compile(rf"({re.escape(label)}\s*[:：]\s*)([^\s，,;；\n\r]+)")
    return pat.sub(rf"\1{replacement}", text)


def sanitize_pii(text: str) -> str:
    s = str(text or "")
    if not s:
        return s

    s = _mask_labeled(s, label="身份证", replacement="【身份证号已脱敏】")
    s = _mask_labeled(s, label="身份证号", replacement="【身份证号已脱敏】")
    s = _mask_labeled(s, label="手机号", replacement="【手机号已脱敏】")
    s = _mask_labeled(s, label="电话", replacement="【手机号已脱敏】")
    s = _mask_labeled(s, label="邮箱", replacement="【邮箱已脱敏】")
    s = _mask_labeled(s, label="银行卡", replacement="【银行卡号已脱敏】")
    s = _mask_labeled(s, label="银行卡号", replacement="【银行卡号已脱敏】")
    s = _mask_labeled(s, label="地址", replacement="【地址已脱敏】")
    s = _mask_labeled(s, label="姓名", replacement="【姓名已脱敏】")

    s = _EMAIL_RE.sub("【邮箱已脱敏】", s)
    s = _ID18_RE.sub("【身份证号已脱敏】", s)
    s = _ID15_RE.sub("【身份证号已脱敏】", s)
    s = _PHONE_RE.sub("【手机号已脱敏】", s)

    # Bank card numbers (heuristic): 16-19 digits, not already replaced, not phone (11) and not ID.
    def _bank_repl(m: re.Match[str]) -> str:
        digits = m.group(0)
        if len(digits) == 11 and digits.startswith("1"):
            return digits
        if len(digits) in {15, 18}:
            return digits
        return "【银行卡号已脱敏】"

    s = re.sub(r"(?<!\d)(\d{16,19})(?!\d)", _bank_repl, s)

    return s
