import sys
from types import SimpleNamespace

import pytest

import app.services.contract_review_service as svc


def test_extract_json_from_fenced_block_and_raw_json():
    text1 = "prefix```json\n{\"a\": 1, \"b\": \"x\"}\n```suffix"
    assert svc._extract_json(text1) == {"a": 1, "b": "x"}

    text2 = "{\"k\": \"v\"}"
    assert svc._extract_json(text2) == {"k": "v"}

    text3 = "```\n{\"x\": 2}\n```"
    assert svc._extract_json(text3) == {"x": 2}


def test_extract_json_returns_none_on_invalid_or_empty():
    assert svc._extract_json("") is None
    assert svc._extract_json("no json here") is None
    assert svc._extract_json("{a:1}") is None


def test_render_contract_review_markdown_includes_sections():
    report = {
        "contract_type": "劳动合同",
        "summary": "总体风险可控。",
        "overall_risk_level": "medium",
        "risks": [
            {"title": "违约责任", "severity": "high", "problem": "条款不清", "suggestion": "明确违约金"},
            "not-a-dict",
        ],
        "missing_clauses": ["争议解决"],
        "recommended_edits": [
            {"clause": "付款", "before": "甲方付款", "after": "甲方应在7日内付款"},
            123,
        ],
        "questions_to_confirm": ["是否存在补充协议？"],
    }

    md = svc.render_contract_review_markdown(report)

    assert md.startswith("# 合同风险体检报告")
    assert "**合同类型**：劳动合同" in md
    assert "**总体风险等级**：medium" in md
    assert "## 总结" in md
    assert "总体风险可控" in md
    assert "## 主要风险点" in md
    assert "### 1. 违约责任（high）" in md
    assert "- 问题：条款不清" in md
    assert "- 建议：明确违约金" in md
    assert "## 可能缺失的条款" in md
    assert "- 争议解决" in md
    assert "## 建议修改稿" in md
    assert "**原文**：" in md
    assert "**建议改为**：" in md
    assert "## 需要进一步确认的问题" in md
    assert "- 是否存在补充协议？" in md


def test_build_contract_review_prompt_includes_focus_and_rules_json():
    sys_prompt, user_prompt = svc.build_contract_review_prompt(
        extracted_text="合同正文",
        focus="我关注违约条款",
        rules={"required_clauses": ["违约责任"]},
    )

    assert "你必须输出严格的 JSON" in sys_prompt
    assert "以下是系统配置的条款库/风险库规则" in sys_prompt
    assert "用户关注点" in user_prompt
    assert "我关注违约条款" in user_prompt


def test_build_contract_review_prompt_ignores_unserializable_rules():
    sys_prompt, _ = svc.build_contract_review_prompt(
        extracted_text="合同正文",
        focus=None,
        rules={"x": set([1])},
    )

    assert "你必须输出严格的 JSON" in sys_prompt
    assert "以下是系统配置的条款库/风险库规则" not in sys_prompt


def test_apply_contract_review_rules_adds_missing_and_risks_and_sets_overall_level():
    report = {
        "missing_clauses": ["争议解决"],
        "risks": [],
    }

    rules = {
        "required_clauses": [
            "违约责任",
            {"name": "争议解决", "patterns": ["仲裁", "诉讼"]},
            {"name": "不可抗力", "patterns": []},
            {"name": "", "patterns": ["x"]},
            123,
        ],
        "risk_keywords": [
            {
                "keyword": "保密",
                "title": "保密义务",
                "severity": "high",
                "problem": "范围过窄",
                "suggestion": "扩大保密范围",
            },
            {"keyword": "罚款", "title": "罚款条款", "severity": "unknown"},
            {"keyword": "不出现", "title": "should_skip", "severity": "high"},
        ],
    }

    text = "本合同约定仲裁解决争议，双方应承担保密义务，不得泄露。"
    out = svc.apply_contract_review_rules(report, extracted_text=text, rules=rules)

    assert "违约责任" in out.get("missing_clauses", [])
    assert out.get("missing_clauses", []).count("争议解决") == 1

    risks = out.get("risks")
    assert isinstance(risks, list)
    titles = [r.get("title") for r in risks if isinstance(r, dict)]
    assert "保密义务" in titles
    assert "罚款条款" not in titles

    assert out.get("overall_risk_level") == "high"


def test_apply_contract_review_rules_merges_overall_level_upwards():
    report = {
        "overall_risk_level": "low",
        "missing_clauses": [],
        "risks": [],
    }

    rules = {
        "risk_keywords": [
            {"keyword": "重大", "title": "重大违约", "severity": "high"},
        ]
    }

    out = svc.apply_contract_review_rules(report, extracted_text="存在重大违约风险", rules=rules)
    assert out.get("overall_risk_level") == "high"


def test_apply_contract_review_rules_returns_early_on_blank_text_or_no_rules():
    report = {"missing_clauses": ["x"]}

    assert svc.apply_contract_review_rules(report, extracted_text="", rules={"required_clauses": ["y"]}) == report
    assert svc.apply_contract_review_rules(report, extracted_text="hi", rules=None) == report


def test_call_openai_contract_review_parses_json_and_renders_markdown(monkeypatch):
    class DummyRes:
        def __init__(self, content):
            self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]

    class DummyCompletions:
        def __init__(self, content):
            self._content = content

        def create(self, **_kwargs):
            return DummyRes(self._content)

    class DummyClient:
        def __init__(self, content):
            self.chat = SimpleNamespace(completions=DummyCompletions(content))

    class DummyOpenAI:
        def __init__(self, **_kwargs):
            self.chat = DummyClient(
                "```json\n{\"contract_type\":\"劳动合同\",\"summary\":\"ok\"}\n```"
            ).chat

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    monkeypatch.setattr(
        svc,
        "settings",
        SimpleNamespace(openai_api_key="k", openai_base_url="http://x", ai_model="gpt-test"),
        raising=True,
    )

    obj, md = svc.call_openai_contract_review(extracted_text="合同正文", focus=None, rules=None)

    assert obj.get("contract_type") == "劳动合同"
    assert md.startswith("# 合同风险体检报告")
    assert "**合同类型**：劳动合同" in md


def test_call_openai_contract_review_handles_empty_choices(monkeypatch):
    class DummyRes:
        def __init__(self):
            self.choices = []

    class DummyClient:
        class _Chat:
            class _Completions:
                def create(self, **_kwargs):
                    return DummyRes()

            completions = _Completions()

        chat = _Chat()

    class DummyOpenAI:
        def __init__(self, **_kwargs):
            self.chat = DummyClient.chat

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    monkeypatch.setattr(
        svc,
        "settings",
        SimpleNamespace(openai_api_key="k", openai_base_url="http://x", ai_model="gpt-test"),
        raising=True,
    )

    obj, md = svc.call_openai_contract_review(extracted_text="合同正文", focus=None, rules=None)
    assert obj == {}
    assert md == ""


def test_call_openai_contract_review_falls_back_to_raw_text_when_json_invalid(monkeypatch):
    class DummyRes:
        def __init__(self, content):
            self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]

    class DummyCompletions:
        def __init__(self, content):
            self._content = content

        def create(self, **_kwargs):
            return DummyRes(self._content)

    class DummyOpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=DummyCompletions("not json"))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=DummyOpenAI))
    monkeypatch.setattr(
        svc,
        "settings",
        SimpleNamespace(openai_api_key="k", openai_base_url="http://x", ai_model="gpt-test"),
        raising=True,
    )

    obj, md = svc.call_openai_contract_review(extracted_text="合同正文", focus=None, rules=None)
    assert obj == {}
    assert md == "not json\n"
