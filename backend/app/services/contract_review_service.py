from __future__ import annotations

import json
import re
from typing import Any

from ..config import get_settings

settings = get_settings()


_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None

    m = _JSON_BLOCK_RE.search(raw)
    if m:
        candidate = m.group(1)
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

    candidate = raw
    if candidate.startswith("```"):
        candidate = candidate.strip("`\n ")

    left = candidate.find("{")
    right = candidate.rfind("}")
    if left >= 0 and right > left:
        candidate2 = candidate[left : right + 1]
        try:
            obj = json.loads(candidate2)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def render_contract_review_markdown(report: dict[str, Any]) -> str:
    contract_type = str(report.get("contract_type") or "").strip()
    summary = str(report.get("summary") or "").strip()
    level = str(report.get("overall_risk_level") or report.get("risk_level") or "").strip()

    md: list[str] = []
    md.append("# 合同风险体检报告")
    if contract_type:
        md.append(f"\n**合同类型**：{contract_type}")
    if level:
        md.append(f"\n**总体风险等级**：{level}")

    if summary:
        md.append("\n## 总结")
        md.append(summary)

    risks = _as_list(report.get("risks"))
    if risks:
        md.append("\n## 主要风险点")
        for i, item in enumerate(risks[:20], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "风险点").strip() or "风险点"
            sev = str(item.get("severity") or "").strip()
            problem = str(item.get("problem") or "").strip()
            suggestion = str(item.get("suggestion") or "").strip()
            md.append(f"\n### {i}. {title}{f'（{sev}）' if sev else ''}")
            if problem:
                md.append(f"- 问题：{problem}")
            if suggestion:
                md.append(f"- 建议：{suggestion}")

    missing = _as_list(report.get("missing_clauses"))
    if missing:
        md.append("\n## 可能缺失的条款")
        for item in missing[:20]:
            s = str(item).strip()
            if s:
                md.append(f"- {s}")

    edits = _as_list(report.get("recommended_edits"))
    if edits:
        md.append("\n## 建议修改稿")
        for i, item in enumerate(edits[:10], start=1):
            if not isinstance(item, dict):
                continue
            clause = str(item.get("clause") or "条款").strip() or "条款"
            before = str(item.get("before") or "").strip()
            after = str(item.get("after") or "").strip()
            md.append(f"\n### {i}. {clause}")
            if before:
                md.append("\n**原文**：")
                md.append(f"\n```\n{before}\n```")
            if after:
                md.append("\n**建议改为**：")
                md.append(f"\n```\n{after}\n```")

    qs = _as_list(report.get("questions_to_confirm"))
    if qs:
        md.append("\n## 需要进一步确认的问题")
        for item in qs[:20]:
            s = str(item).strip()
            if s:
                md.append(f"- {s}")

    return "\n".join(md).strip() + "\n"


def build_contract_review_prompt(*, extracted_text: str, focus: str | None) -> tuple[str, str]:
    sys = (
        "你是专业的合同审查律师助理。"
        "你必须输出严格的 JSON（不要输出多余解释文字）。"
        "JSON 字段：contract_type, summary, overall_risk_level(low/medium/high), "
        "risks([{title,severity(low/medium/high),problem,suggestion}]), "
        "missing_clauses([string]), recommended_edits([{clause,before,after}]), questions_to_confirm([string])."
        "如果无法确定，字段可以为空字符串或空数组，但必须是合法 JSON。"
    )

    user_lines = ["以下是合同文本（可能已脱敏）：", extracted_text]
    focus_norm = str(focus or "").strip()
    if focus_norm:
        user_lines.append("\n用户关注点：")
        user_lines.append(focus_norm)

    user = "\n".join(user_lines)
    return sys, user


def call_openai_contract_review(*, extracted_text: str, focus: str | None = None) -> tuple[dict[str, Any], str]:
    from openai import OpenAI

    sys, user = build_contract_review_prompt(extracted_text=extracted_text, focus=focus)

    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    model = str(settings.ai_model or "").strip() or "gpt-4o-mini"

    res = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=1400,
    )

    choices = getattr(res, "choices", None)
    if not choices:
        return {}, ""

    msg = getattr(choices[0], "message", None)
    content = str(getattr(msg, "content", "") or "")

    obj = _extract_json(content) or {}
    md = render_contract_review_markdown(obj) if obj else (content.strip() + "\n")
    return obj, md
