from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class SafetyCheckResult:
    risk_level: RiskLevel
    triggered_rules: list[str]
    suggestion: str | None = None
    should_log: bool = False


class ContentSafetyFilter:
    BLOCKED_PATTERNS: list[str] = [
        r"如何.*杀人",
        r"怎么.*报复",
        r"教.*制造.*武器",
        r"如何.*洗钱",
    ]

    HIGH_RISK_KEYWORDS: list[str] = [
        "自杀",
        "自残",
        "极端",
        "报复社会",
    ]

    SENSITIVE_TOPICS: dict[str, list[str]] = {
        "政治敏感": [r"国家.*领导", r"政府.*腐败"],
        "人身安全": [r"威胁", r"恐吓"],
        "隐私侵犯": [r"人肉搜索", r"曝光.*个人信息"],
    }

    def check_input(self, text: str) -> SafetyCheckResult:
        s = str(text or "")
        triggered: list[str] = []

        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, s, re.IGNORECASE):
                return SafetyCheckResult(
                    risk_level=RiskLevel.BLOCKED,
                    triggered_rules=[f"blocked:{pattern}"],
                    suggestion="很抱歉，我无法回答这类问题。如需帮助，请联系专业机构。",
                    should_log=True,
                )

        for keyword in self.HIGH_RISK_KEYWORDS:
            if keyword in s:
                triggered.append(f"high_risk:{keyword}")

        if triggered:
            return SafetyCheckResult(
                risk_level=RiskLevel.HIGH,
                triggered_rules=triggered,
                suggestion="您的问题涉及敏感内容，我会谨慎回答。如遇紧急情况请拨打110或相关求助热线。",
                should_log=True,
            )

        for topic, patterns in self.SENSITIVE_TOPICS.items():
            for pattern in patterns:
                if re.search(pattern, s, re.IGNORECASE):
                    triggered.append(f"sensitive:{topic}")

        if triggered:
            return SafetyCheckResult(
                risk_level=RiskLevel.MEDIUM,
                triggered_rules=triggered,
                suggestion=None,
                should_log=True,
            )

        return SafetyCheckResult(risk_level=RiskLevel.SAFE, triggered_rules=[])

    def sanitize_output(self, text: str) -> str:
        s = str(text or "")
        s = re.sub(r"(?<!\d)\d{11}(?!\d)", "[电话号码已隐藏]", s)
        s = re.sub(r"(?<!\d)\d{18}(?!\d)", "[身份证号已隐藏]", s)
        return s
