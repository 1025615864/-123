"""法律文书生成API路由"""
import os
import time
import urllib.parse
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime
import json

from ..database import get_db
from ..models.document import GeneratedDocument
from ..models.document_template import DocumentTemplate, DocumentTemplateVersion
from ..models.user import User
from ..utils.deps import get_current_user_optional, get_current_user
from ..utils.rate_limiter import rate_limit, RateLimitConfig, rate_limiter, get_client_ip
from ..services.quota_service import quota_service
from ..services.document_templates_builtin import BUILTIN_DOCUMENT_TEMPLATES

router = APIRouter(prefix="/documents", tags=["文书生成"])


def _get_int_env(key: str, default: int) -> int:
    raw = os.getenv(key, "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


GUEST_DOCUMENT_GENERATE_LIMIT = _get_int_env("GUEST_DOCUMENT_GENERATE_LIMIT", 0)
GUEST_DOCUMENT_GENERATE_WINDOW_SECONDS = _get_int_env(
    "GUEST_DOCUMENT_GENERATE_WINDOW_SECONDS", 60 * 60 * 24
)


async def _enforce_guest_document_quota(request: Request) -> None:
    if int(GUEST_DOCUMENT_GENERATE_LIMIT) <= 0:
        return

    key = f"doc:guest:{get_client_ip(request)}"
    allowed, remaining, wait_time = await rate_limiter.check(
        key,
        int(GUEST_DOCUMENT_GENERATE_LIMIT),
        int(GUEST_DOCUMENT_GENERATE_WINDOW_SECONDS),
    )
    if allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="游客模式文书生成次数已用尽，请登录后继续",
        headers={
            "X-RateLimit-Limit": str(int(GUEST_DOCUMENT_GENERATE_LIMIT)),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(int(time.time() + wait_time)),
            "Retry-After": str(int(wait_time)),
        },
    )


class DocumentGenerateRequest(BaseModel):
    """文书生成请求"""
    document_type: str  # complaint (起诉状), defense (答辩状), agreement (协议书), letter (律师函)
    case_type: str  # 案件类型：劳动纠纷、合同纠纷、婚姻家庭等
    plaintiff_name: str  # 原告/甲方姓名
    defendant_name: str  # 被告/乙方姓名
    facts: str  # 案件事实
    claims: str  # 诉讼请求/主要诉求
    evidence: str | None = None  # 证据说明
    extra_info: dict[str, str] | None = None  # 其他信息


class DocumentResponse(BaseModel):
    """文书生成响应"""
    document_type: str
    title: str
    content: str
    created_at: datetime
    template_key: str | None = None
    template_version: int | None = None


class DocumentExportPdfRequest(BaseModel):
    title: str
    content: str


# 文书模板
DOCUMENT_TEMPLATES = {
    "complaint": {
        "title": "民事起诉状",
        "template": """民事起诉状

原告：{plaintiff_name}

被告：{defendant_name}

诉讼请求：
{claims}

事实与理由：
{facts}

{evidence_section}

此致
{court_name}

具状人：{plaintiff_name}
{date}

附：本诉状副本 1 份
    证据材料 {evidence_count} 份"""
    },
    "defense": {
        "title": "民事答辩状",
        "template": """民事答辩状

答辩人：{defendant_name}
被答辩人：{plaintiff_name}

答辩人就被答辩人诉答辩人{case_type}一案，现提出如下答辩意见：

一、案件基本情况
{facts}

二、答辩意见
{claims}

{evidence_section}

综上所述，答辩人认为被答辩人的诉讼请求缺乏事实和法律依据，请求法院依法驳回。

此致
{court_name}

答辩人：{defendant_name}
{date}"""
    },
    "agreement": {
        "title": "和解协议书",
        "template": """和解协议书

甲方：{plaintiff_name}
乙方：{defendant_name}

鉴于甲乙双方因{case_type}发生纠纷，为妥善解决争议，经双方友好协商，达成如下协议：

一、争议事项
{facts}

二、协议内容
{claims}

三、其他约定
1. 本协议自双方签字之日起生效。
2. 本协议一式两份，甲乙双方各执一份，具有同等法律效力。
3. 双方承诺不再就本纠纷向任何机构提起诉讼或仲裁。

甲方（签字）：_______________    乙方（签字）：_______________

日期：{date}                    日期：{date}"""
    },
    "letter": {
        "title": "律师函",
        "template": """律师函

致：{defendant_name}

本函由{plaintiff_name}委托发出。

事由：关于{case_type}事宜

一、基本事实
{facts}

二、法律意见与要求
{claims}

三、法律后果告知
如贵方收到本函后仍不履行上述义务，委托人将依法采取以下措施：
1. 向有管辖权的人民法院提起诉讼；
2. 主张因此产生的全部损失及维权费用；
3. 依法追究相关法律责任。

请贵方在收到本函之日起【7】个工作日内，与委托人联系协商解决方案。

特此函告。

委托人：{plaintiff_name}
{date}"""
    }
}


async def _get_published_document_template(
    db: AsyncSession, *, template_key: str
) -> tuple[str, str | None, str, int] | None:
    key = str(template_key or "").strip()
    if not key:
        return None

    tpl_res = await db.execute(
        select(DocumentTemplate).where(
            DocumentTemplate.key == key,
            DocumentTemplate.is_active.is_(True),
        )
    )
    tpl = tpl_res.scalar_one_or_none()
    if tpl is None:
        return None

    ver_res = await db.execute(
        select(DocumentTemplateVersion)
        .where(
            DocumentTemplateVersion.template_id == int(tpl.id),
            DocumentTemplateVersion.is_published.is_(True),
        )
        .order_by(DocumentTemplateVersion.version.desc())
        .limit(1)
    )
    ver = ver_res.scalar_one_or_none()
    if ver is None:
        return None

    content = str(ver.content or "").strip()
    if not content:
        return None

    return (str(tpl.title), tpl.description, content, int(ver.version))


def _escape_pdf_paragraph(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _generate_document_pdf(*, title: str, content: str) -> bytes:
    try:
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except Exception as e:
        raise RuntimeError("PDF_DEPENDENCY_MISSING") from e

    class _PdfMetrics(Protocol):
        def registerFont(self, font: object) -> None: ...

    class _DocBuilder(Protocol):
        def build(self, flowables: list[object]) -> None: ...

    cast(_PdfMetrics, cast(object, pdfmetrics)).registerFont(UnicodeCIDFont("STSong-Light"))

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="DocTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=18,
        leading=24,
        alignment=1,
        spaceAfter=14,
    )
    meta_style = ParagraphStyle(
        name="DocMeta",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=9,
        leading=14,
        textColor=colors.grey,
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        name="DocBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=11,
        leading=18,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    safe_title = str(title or "法律文书").strip() or "法律文书"
    safe_content = str(content or "").strip()

    story: list[object] = []
    story.append(Paragraph(_escape_pdf_paragraph(safe_title), title_style))
    story.append(Paragraph(_escape_pdf_paragraph(datetime.now().strftime("%Y年%m月%d日")), meta_style))
    if safe_content:
        story.append(Paragraph(_escape_pdf_paragraph(safe_content), body_style))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            _escape_pdf_paragraph(
                "免责声明：本文书由系统生成，仅供参考。正式使用前，请务必咨询专业律师进行审核和修改。"
            ),
            meta_style,
        )
    )

    cast(_DocBuilder, cast(object, doc)).build(story)
    _ = buf.seek(0)
    return buf.getvalue()


@router.post("/generate", response_model=DocumentResponse)
@rate_limit(*RateLimitConfig.DOCUMENT_GENERATE, by_ip=True, by_user=False)
async def generate_document(
    data: DocumentGenerateRequest,
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """生成法律文书"""
    if current_user is None:
        await _enforce_guest_document_quota(request)
    else:
        await quota_service.enforce_document_generate_quota(db, current_user)

    if len(data.facts) > 8000 or len(data.claims) > 4000 or (data.evidence and len(data.evidence) > 4000):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="输入内容过长，请缩短事实/诉求/证据描述"
        )

    template_key = str(data.document_type or "").strip()
    if not template_key:
        raise HTTPException(status_code=400, detail="document_type 不能为空")

    template_title: str | None = None
    template_content: str | None = None
    template_version: int | None = None

    db_template = await _get_published_document_template(db, template_key=template_key)
    if db_template is not None:
        template_title, _desc, template_content, template_version = db_template
    else:
        builtin = BUILTIN_DOCUMENT_TEMPLATES.get(template_key)
        if builtin is not None:
            template_title = str(builtin.get("title") or template_key)
            template_content = str(builtin.get("template") or "").strip() or None

    if template_content is None or template_title is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文书类型: {template_key}",
        )
    
    # 准备证据部分
    evidence_section = ""
    evidence_count = 0
    if data.evidence:
        evidence_section = f"证据及证据说明：\n{data.evidence}"
        evidence_count = len(data.evidence.split('\n'))
    
    # 根据案件类型确定法院名称
    court_name = "人民法院"
    
    # 格式化日期
    date_str = datetime.now().strftime("%Y年%m月%d日")
    
    # 填充模板
    content = template_content.format(
        plaintiff_name=data.plaintiff_name,
        defendant_name=data.defendant_name,
        case_type=data.case_type,
        facts=data.facts,
        claims=data.claims,
        evidence_section=evidence_section,
        evidence_count=evidence_count if evidence_count > 0 else "若干",
        court_name=court_name,
        date=date_str,
    )
    
    if current_user is not None:
        try:
            await quota_service.record_document_generate_usage(db, current_user)
        except Exception:
            pass

    return DocumentResponse(
        document_type=template_key,
        title=template_title,
        content=content,
        created_at=datetime.now(),
        template_key=template_key,
        template_version=template_version,
    )


@router.post("/export/pdf")
@rate_limit(*RateLimitConfig.DOCUMENT_GENERATE, by_ip=True, by_user=False)
async def export_document_pdf(
    data: DocumentExportPdfRequest,
):
    try:
        pdf_bytes = _generate_document_pdf(title=str(data.title or "").strip(), content=str(data.content or ""))
    except RuntimeError as e:
        if str(e) == "PDF_DEPENDENCY_MISSING":
            raise HTTPException(status_code=501, detail="PDF 生成依赖未安装")
        raise

    ascii_filename = "document.pdf"
    utf8_filename = f"{str(data.title or '法律文书').strip() or '法律文书'}.pdf"
    quoted_utf8 = urllib.parse.quote(utf8_filename, safe="")
    content_disposition = (
        f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{quoted_utf8}"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition,
        },
    )


@router.get("/types")
async def get_document_types(db: Annotated[AsyncSession, Depends(get_db)]):
    """获取支持的文书类型"""
    try:
        res = await db.execute(
            select(DocumentTemplate).where(DocumentTemplate.is_active.is_(True)).order_by(DocumentTemplate.id.asc())
        )
        templates = res.scalars().all()

        out: list[dict[str, str]] = []
        for t in templates:
            ver_res = await db.execute(
                select(DocumentTemplateVersion)
                .where(
                    DocumentTemplateVersion.template_id == int(t.id),
                    DocumentTemplateVersion.is_published.is_(True),
                )
                .order_by(DocumentTemplateVersion.version.desc())
                .limit(1)
            )
            published = ver_res.scalar_one_or_none()
            if published is None:
                continue
            out.append(
                {
                    "type": str(t.key),
                    "name": str(t.title),
                    "description": str(t.description or ""),
                }
            )

        if out:
            return out
    except Exception:
        pass

    return [
        {
            "type": str(key),
            "name": str(meta.get("title") or key),
            "description": str(meta.get("description") or ""),
        }
        for key, meta in BUILTIN_DOCUMENT_TEMPLATES.items()
    ]


class DocumentSaveRequest(BaseModel):
    document_type: str
    title: str
    content: str
    payload: dict[str, object] | None = None
    template_key: str | None = None
    template_version: int | None = None


class DocumentItem(BaseModel):
    id: int
    document_type: str
    title: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentItem]
    total: int


@router.post("/save")
async def save_document(
    data: DocumentSaveRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    payload_json: str | None = None
    if data.payload is not None:
        try:
            payload_json = json.dumps(data.payload, ensure_ascii=False)
        except Exception:
            payload_json = None

    template_key = str(data.template_key or data.document_type or "").strip() or None
    template_version: int | None = None
    if data.template_version is not None:
        try:
            template_version = int(data.template_version)
        except Exception:
            template_version = None

    if template_version is None and template_key:
        try:
            published = await _get_published_document_template(db, template_key=template_key)
            if published is not None:
                template_version = int(published[3])
        except Exception:
            template_version = None

    doc = GeneratedDocument(
        user_id=current_user.id,
        document_type=str(data.document_type or "").strip(),
        title=str(data.title or "").strip() or "法律文书",
        content=str(data.content or "").strip(),
        template_key=template_key,
        template_version=template_version,
        payload_json=payload_json,
    )
    if not doc.document_type:
        raise HTTPException(status_code=400, detail="document_type 不能为空")
    if not doc.content:
        raise HTTPException(status_code=400, detail="content 不能为空")

    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {"id": int(doc.id), "message": "保存成功"}


@router.get("/my", response_model=DocumentListResponse)
async def list_my_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 20,
):
    page = max(1, int(page))
    page_size = max(1, min(100, int(page_size)))

    base = select(GeneratedDocument).where(GeneratedDocument.user_id == current_user.id)
    count_query = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_query)
    total = int(total_result.scalar() or 0)

    q = base.order_by(GeneratedDocument.created_at.desc(), GeneratedDocument.id.desc())
    q = q.offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(q)
    rows = res.scalars().all()

    items = [
        DocumentItem(
            id=int(x.id),
            document_type=str(x.document_type),
            title=str(x.title),
            created_at=x.created_at,
        )
        for x in rows
    ]
    return DocumentListResponse(items=items, total=total)


@router.get("/my/{doc_id}")
async def get_my_document(
    doc_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    res = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == int(doc_id),
            GeneratedDocument.user_id == current_user.id,
        )
    )
    doc = res.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="文书不存在")

    return {
        "id": int(doc.id),
        "user_id": int(doc.user_id),
        "document_type": str(doc.document_type),
        "title": str(doc.title),
        "content": str(doc.content),
        "payload_json": doc.payload_json,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


@router.get("/my/{doc_id}/export")
async def export_my_document(
    doc_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: Annotated[str, Query(max_length=10)] = "pdf",
):
    fmt = str(format or "").strip().lower()
    if fmt != "pdf":
        raise HTTPException(status_code=400, detail="暂不支持该格式")

    res = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == int(doc_id),
            GeneratedDocument.user_id == current_user.id,
        )
    )
    doc = res.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="文书不存在")

    title = str(doc.title or "法律文书").strip() or "法律文书"
    content = str(doc.content or "")
    try:
        pdf_bytes = _generate_document_pdf(title=title, content=content)
    except RuntimeError as e:
        if str(e) == "PDF_DEPENDENCY_MISSING":
            raise HTTPException(status_code=501, detail="PDF 生成依赖未安装")
        raise

    ascii_filename = "document.pdf"
    utf8_filename = f"{title}.pdf"
    quoted_utf8 = urllib.parse.quote(utf8_filename, safe="")
    content_disposition = (
        f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{quoted_utf8}"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition,
        },
    )


@router.delete("/my/{doc_id}")
async def delete_my_document(
    doc_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    res = await db.execute(
        select(GeneratedDocument).where(
            GeneratedDocument.id == int(doc_id),
            GeneratedDocument.user_id == current_user.id,
        )
    )
    doc = res.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="文书不存在")

    await db.delete(doc)
    await db.commit()
    return {"message": "删除成功"}
