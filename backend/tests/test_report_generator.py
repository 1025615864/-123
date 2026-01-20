import builtins
from datetime import datetime

import pytest

from app.services.report_generator import (
    ConsultationReport,
    _escape_paragraph,
    build_consultation_report_from_export_data,
    generate_consultation_report_pdf,
)


def test_build_consultation_report_from_export_data_parses_and_dedupes_laws():
    export_data = {
        "session_id": "s1",
        "title": "测试咨询",
        "created_at": "2026-01-19T10:20:30",
        "messages": [
            {"role": "user", "content": "  我想咨询劳动合同问题  "},
            {"role": "assistant", "content": "  先确认下合同主体与签署时间。  "},
            {"role": "user", "content": "还有拖欠工资"},
            {"role": "user", "content": "想问仲裁时效"},
            {"role": "user", "content": "第四条用户消息（应被 key_issues 截断）"},
            {"role": "user", "content": "   "},
            {"role": "assistant", "content": "   "},
            "not-a-dict",
            {
                "role": "assistant",
                "content": "补充说明",
                "references": [
                    "bad-ref",
                    {
                        "law_name": "劳动合同法",
                        "article": "第十条",
                        "content": "建立劳动关系，应当订立书面劳动合同。",
                    },
                    {
                        "law_name": "劳动合同法",
                        "article": "第十条",
                        "content": "这条重复，不应覆盖前一个",
                    },
                    {"law_name": "劳动合同法", "article": "", "content": "缺少条款号"},
                    {"law_name": "", "article": "第十条", "content": "缺少法名"},
                ],
            },
        ],
    }

    report = build_consultation_report_from_export_data(export_data, user_name="张三")

    assert isinstance(report, ConsultationReport)
    assert report.session_id == "s1"
    assert report.title == "测试咨询"
    assert report.user_name == "张三"
    assert report.created_at == datetime.fromisoformat("2026-01-19T10:20:30")

    assert report.summary == "我想咨询劳动合同问题\n\n先确认下合同主体与签署时间。"
    assert report.key_issues == ["我想咨询劳动合同问题", "还有拖欠工资", "想问仲裁时效"]

    assert len(report.referenced_laws) == 1
    assert report.referenced_laws[0]["law_name"] == "劳动合同法"
    assert report.referenced_laws[0]["article"] == "第十条"
    assert "订立书面劳动合同" in report.referenced_laws[0]["content"]


def test_build_consultation_report_from_export_data_defaults_when_missing_user_messages():
    export_data = {
        "session_id": "",
        "created_at": "not-iso",
        "messages": [
            {"role": "assistant", "content": "这是助手的开场回复"},
        ],
    }

    report = build_consultation_report_from_export_data(export_data, user_name="")

    assert report.title == "法律咨询"
    assert report.created_at is None
    assert report.user_name == "用户"

    assert report.summary == "这是助手的开场回复"
    assert report.key_issues == ["请结合对话内容补充核心问题描述。"]


def test_escape_paragraph_replaces_chars_and_newlines():
    assert _escape_paragraph("a&b<c>d\nline2") == "a&amp;b&lt;c&gt;d<br/>line2"


def test_generate_consultation_report_pdf_dependency_missing(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if str(name).startswith("reportlab"):
            raise ModuleNotFoundError("No module named 'reportlab'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    report = ConsultationReport(
        session_id="s1",
        title="t",
        created_at=None,
        user_name="u",
        summary="s",
        key_issues=["i"],
        recommendations=["r"],
        referenced_laws=[],
    )

    with pytest.raises(RuntimeError) as exc:
        _ = generate_consultation_report_pdf(report)

    assert str(exc.value) == "PDF_DEPENDENCY_MISSING"


def test_generate_consultation_report_pdf_success_smoke():
    _ = pytest.importorskip("reportlab")

    report = ConsultationReport(
        session_id="s1",
        title="t",
        created_at=None,
        user_name="u",
        summary="s",
        key_issues=["i"],
        recommendations=["r"],
        referenced_laws=[],
    )

    data = generate_consultation_report_pdf(report)
    assert isinstance(data, (bytes, bytearray))
    assert bytes(data)[:4] == b"%PDF"


def test_generate_consultation_report_pdf_success_with_referenced_laws_smoke():
    _ = pytest.importorskip("reportlab")

    report = ConsultationReport(
        session_id="s1",
        title="t",
        created_at=None,
        user_name="u",
        summary="s",
        key_issues=["i"],
        recommendations=["r"],
        referenced_laws=[
            {"law_name": "劳动合同法", "article": "第十条", "content": "建立劳动关系，应当订立书面劳动合同。"}
        ],
    )

    data = generate_consultation_report_pdf(report)
    assert isinstance(data, (bytes, bytearray))
    assert bytes(data)[:4] == b"%PDF"
