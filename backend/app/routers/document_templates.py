from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.document_template import DocumentTemplate, DocumentTemplateVersion
from ..models.user import User
from ..utils.deps import require_admin

router = APIRouter(prefix="/admin/document-templates", tags=["文书模板管理"])


class DocumentTemplateOut(BaseModel):
    id: int
    key: str
    title: str
    description: str | None
    is_active: bool
    published_version: int | None = None
    created_at: datetime
    updated_at: datetime


class DocumentTemplateCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class DocumentTemplateUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class DocumentTemplateVersionOut(BaseModel):
    id: int
    template_id: int
    version: int
    is_published: bool
    content: str
    created_at: datetime


class DocumentTemplateVersionCreate(BaseModel):
    content: str = Field(..., min_length=1)
    publish: bool = False


@router.get("", response_model=list[DocumentTemplateOut])
async def list_document_templates(
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    res = await db.execute(select(DocumentTemplate).order_by(DocumentTemplate.id.asc()))
    templates = res.scalars().all()

    out: list[DocumentTemplateOut] = []
    for t in templates:
        template_id = int(t.id)
        pub_res = await db.execute(
            select(func.max(DocumentTemplateVersion.version)).where(
                DocumentTemplateVersion.template_id == template_id,
                DocumentTemplateVersion.is_published.is_(True),
            )
        )
        published_version = pub_res.scalar_one_or_none()
        out.append(
            DocumentTemplateOut(
                id=template_id,
                key=str(t.key),
                title=str(t.title),
                description=t.description,
                is_active=bool(t.is_active),
                published_version=int(published_version) if published_version is not None else None,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )

    return out


@router.post("", response_model=DocumentTemplateOut)
async def create_document_template(
    data: DocumentTemplateCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    key = str(data.key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="key 不能为空")

    exists_res = await db.execute(select(DocumentTemplate).where(DocumentTemplate.key == key))
    if exists_res.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="key 已存在")

    row = DocumentTemplate(
        key=key,
        title=str(data.title or "").strip() or key,
        description=str(data.description).strip() if data.description is not None else None,
        is_active=bool(data.is_active),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return DocumentTemplateOut(
        id=int(row.id),
        key=str(row.key),
        title=str(row.title),
        description=row.description,
        is_active=bool(row.is_active),
        published_version=None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.put("/{template_id}", response_model=DocumentTemplateOut)
async def update_document_template(
    template_id: int,
    data: DocumentTemplateUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    res = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == int(template_id)))
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="模板不存在")

    if data.title is not None:
        row.title = str(data.title or "").strip() or str(getattr(row, "key"))
    if data.description is not None:
        row.description = str(data.description).strip() if data.description else None
    if data.is_active is not None:
        row.is_active = bool(data.is_active)

    db.add(row)
    await db.commit()
    await db.refresh(row)

    template_id = int(row.id)
    pub_res = await db.execute(
        select(func.max(DocumentTemplateVersion.version)).where(
            DocumentTemplateVersion.template_id == template_id,
            DocumentTemplateVersion.is_published.is_(True),
        )
    )
    published_version = pub_res.scalar_one_or_none()

    return DocumentTemplateOut(
        id=template_id,
        key=str(row.key),
        title=str(row.title),
        description=row.description,
        is_active=bool(row.is_active),
        published_version=int(published_version) if published_version is not None else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/{template_id}/versions", response_model=list[DocumentTemplateVersionOut])
async def list_document_template_versions(
    template_id: int,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    res = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == int(template_id)))
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="模板不存在")

    q = (
        select(DocumentTemplateVersion)
        .where(DocumentTemplateVersion.template_id == int(template_id))
        .order_by(DocumentTemplateVersion.version.desc(), DocumentTemplateVersion.id.desc())
    )
    versions_res = await db.execute(q)
    versions = versions_res.scalars().all()

    return [
        DocumentTemplateVersionOut(
            id=int(v.id),
            template_id=int(v.template_id),
            version=int(v.version),
            is_published=bool(v.is_published),
            content=str(v.content),
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.post("/{template_id}/versions", response_model=DocumentTemplateVersionOut)
async def create_document_template_version(
    template_id: int,
    data: DocumentTemplateVersionCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    tpl_res = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == int(template_id)))
    tpl = tpl_res.scalar_one_or_none()
    if tpl is None:
        raise HTTPException(status_code=404, detail="模板不存在")

    max_res = await db.execute(
        select(func.max(DocumentTemplateVersion.version)).where(DocumentTemplateVersion.template_id == int(template_id))
    )
    max_version = max_res.scalar_one_or_none()
    next_version = int(max_version or 0) + 1

    row = DocumentTemplateVersion(
        template_id=int(template_id),
        version=int(next_version),
        content=str(data.content or "").strip(),
        is_published=bool(data.publish),
    )
    if not row.content:
        raise HTTPException(status_code=400, detail="content 不能为空")

    if bool(data.publish):
        existing_res = await db.execute(
            select(DocumentTemplateVersion).where(DocumentTemplateVersion.template_id == int(template_id))
        )
        for v in existing_res.scalars().all():
            if bool(v.is_published):
                v.is_published = False
                db.add(v)

    db.add(row)
    await db.commit()
    await db.refresh(row)

    return DocumentTemplateVersionOut(
        id=int(row.id),
        template_id=int(row.template_id),
        version=int(row.version),
        is_published=bool(row.is_published),
        content=str(row.content),
        created_at=row.created_at,
    )


@router.post("/{template_id}/versions/{version_id}/publish", response_model=DocumentTemplateVersionOut)
async def publish_document_template_version(
    template_id: int,
    version_id: int,
    current_user: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _ = current_user

    tpl_res = await db.execute(select(DocumentTemplate).where(DocumentTemplate.id == int(template_id)))
    tpl = tpl_res.scalar_one_or_none()
    if tpl is None:
        raise HTTPException(status_code=404, detail="模板不存在")

    ver_res = await db.execute(
        select(DocumentTemplateVersion).where(
            DocumentTemplateVersion.id == int(version_id),
            DocumentTemplateVersion.template_id == int(template_id),
        )
    )
    row = ver_res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="版本不存在")

    existing_res = await db.execute(
        select(DocumentTemplateVersion).where(DocumentTemplateVersion.template_id == int(template_id))
    )
    for v in existing_res.scalars().all():
        if int(v.id) == int(row.id):
            continue
        if bool(v.is_published):
            v.is_published = False
            db.add(v)

    row.is_published = True
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return DocumentTemplateVersionOut(
        id=int(row.id),
        template_id=int(row.template_id),
        version=int(row.version),
        is_published=bool(row.is_published),
        content=str(row.content),
        created_at=row.created_at,
    )
