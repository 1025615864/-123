from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ConsultationReport:
    session_id: str
    title: str
    created_at: datetime | None
    user_name: str
    summary: str
    key_issues: list[str]
    recommendations: list[str]
    referenced_laws: list[dict[str, str]]


def build_consultation_report_from_export_data(
    export_data: dict[str, Any],
    *,
    user_name: str,
) -> ConsultationReport:
    session_id = str(export_data.get("session_id") or "")
    title = str(export_data.get("title") or "法律咨询")

    created_at_raw = export_data.get("created_at")
    created_at: datetime | None = None
    if isinstance(created_at_raw, str) and created_at_raw.strip():
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except ValueError:
            created_at = None

    messages = export_data.get("messages")
    msg_list: list[dict[str, Any]] = messages if isinstance(messages, list) else []

    user_msgs: list[str] = []
    assistant_msgs: list[str] = []
    laws: dict[tuple[str, str], str] = {}

    for m in msg_list:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "")
        content = str(m.get("content") or "")
        if role == "user" and content.strip():
            user_msgs.append(content.strip())
        elif role == "assistant" and content.strip():
            assistant_msgs.append(content.strip())

        refs = m.get("references")
        if isinstance(refs, list):
            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                law_name = str(ref.get("law_name") or "").strip()
                article = str(ref.get("article") or "").strip()
                content_ref = str(ref.get("content") or "").strip()
                if not law_name or not article:
                    continue
                key = (law_name, article)
                if key not in laws and content_ref:
                    laws[key] = content_ref

    summary_parts: list[str] = []
    if user_msgs:
        summary_parts.append(user_msgs[0])
    if assistant_msgs:
        summary_parts.append(assistant_msgs[0])

    summary = "\n\n".join(summary_parts).strip() or "本报告基于咨询对话生成。"

    key_issues = user_msgs[:3] if user_msgs else []
    if not key_issues:
        key_issues = ["请结合对话内容补充核心问题描述。"]

    recommendations: list[str] = [
        "整理关键事实与证据（合同、转账记录、聊天记录、通知/函件等）。",
        "如涉及时效/仲裁期限，请尽快采取行动并保留提交/送达凭证。",
        "如争议金额较大或情况复杂，建议咨询专业律师获取进一步意见。",
    ]

    referenced_laws = [
        {"law_name": k[0], "article": k[1], "content": v}
        for k, v in laws.items()
    ]

    return ConsultationReport(
        session_id=session_id,
        title=title,
        created_at=created_at,
        user_name=str(user_name or "用户"),
        summary=summary,
        key_issues=key_issues,
        recommendations=recommendations,
        referenced_laws=referenced_laws,
    )


def generate_consultation_report_pdf(report: ConsultationReport) -> bytes:
    try:
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as e:
        raise RuntimeError("PDF_DEPENDENCY_MISSING") from e

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=18,
        leading=24,
        alignment=1,
        spaceAfter=16,
    )
    heading_style = ParagraphStyle(
        name="ReportHeading",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=13,
        leading=18,
        spaceBefore=12,
        spaceAfter=8,
        textColor=colors.HexColor("#1a56db"),
    )
    body_style = ParagraphStyle(
        name="ReportBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10,
        leading=16,
        spaceAfter=6,
    )
    small_style = ParagraphStyle(
        name="ReportSmall",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=8,
        leading=12,
        textColor=colors.grey,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    story: list[Any] = []

    story.append(Paragraph("法律咨询报告", title_style))

    created_at_text = report.created_at.strftime("%Y年%m月%d日 %H:%M") if report.created_at else "-"

    info_data = [
        ["咨询编号", report.session_id or "-"],
        ["标题", report.title or "-"],
        ["咨询时间", created_at_text],
        ["用户", report.user_name or "用户"],
    ]
    info_table = Table(info_data, colWidths=[70, 410])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    story.append(info_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("一、问题摘要", heading_style))
    story.append(Paragraph(_escape_paragraph(report.summary), body_style))

    story.append(Paragraph("二、核心问题", heading_style))
    for i, issue in enumerate(report.key_issues, 1):
        story.append(Paragraph(_escape_paragraph(f"{i}. {issue}"), body_style))

    story.append(Paragraph("三、行动建议", heading_style))
    for i, rec in enumerate(report.recommendations, 1):
        story.append(Paragraph(_escape_paragraph(f"{i}. {rec}"), body_style))

    if report.referenced_laws:
        story.append(Paragraph("四、相关法条", heading_style))
        for law in report.referenced_laws[:15]:
            law_name = str(law.get("law_name") or "").strip()
            article = str(law.get("article") or "").strip()
            content = str(law.get("content") or "").strip()
            title = f"《{law_name}》{article}" if law_name or article else "相关法条"
            story.append(Paragraph(_escape_paragraph(title), body_style))
            if content:
                story.append(Paragraph(_escape_paragraph(content), small_style))
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 18))
    story.append(Paragraph("免责声明", heading_style))
    story.append(
        Paragraph(
            _escape_paragraph(
                "本报告基于用户提供的信息与对话内容生成，仅供参考，不构成正式法律意见。具体案件请结合证据材料并咨询专业律师。"
            ),
            small_style,
        )
    )

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def _escape_paragraph(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
