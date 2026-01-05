"""知识库管理API路由"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user import User
from ..schemas.knowledge import (
    KnowledgeType,
    LegalKnowledgeCreate,
    LegalKnowledgeUpdate,
    LegalKnowledgeResponse,
    LegalKnowledgeListResponse,
    ConsultationTemplateCreate,
    ConsultationTemplateUpdate,
    ConsultationTemplateResponse,
    KnowledgeStats,
    BatchVectorizeRequest,
    BatchDeleteRequest,
    BatchOperationResponse,
    BatchImportKnowledgeRequest,
    BatchImportKnowledgeResponse,
)
from ..services.knowledge_service import get_knowledge_service, KnowledgeService
from ..utils.deps import require_admin, get_current_user_optional

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])


# === 法律知识 API ===

@router.post("/laws", response_model=LegalKnowledgeResponse)
async def create_knowledge(
    data: LegalKnowledgeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """
    创建法律知识条目
    
    - **knowledge_type**: 知识类型 (law/case/regulation/interpretation)
    - **title**: 标题（法律名称或案例名称）
    - **article_number**: 条款编号（可选）
    - **content**: 内容
    - **category**: 分类（如：民法、刑法、劳动法）
    """
    _ = current_user
    knowledge = await service.create_knowledge(db, data)
    return knowledge


@router.get("/laws", response_model=LegalKnowledgeListResponse)
async def list_knowledge(
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1, description="页码")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
    knowledge_type: Annotated[str | None, Query(description="知识类型过滤")] = None,
    category: Annotated[str | None, Query(description="分类过滤")] = None,
    keyword: Annotated[str | None, Query(description="关键词搜索")] = None,
    is_active: Annotated[bool | None, Query(description="是否启用")] = None,
):
    """
    获取法律知识列表
    
    支持分页、类型过滤、分类过滤、关键词搜索
    """
    _ = current_user
    items, total = await service.list_knowledge(
        db, page, page_size, knowledge_type, category, keyword, is_active
    )
    return LegalKnowledgeListResponse(
        items=[LegalKnowledgeResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/laws/{knowledge_id}", response_model=LegalKnowledgeResponse)
async def get_knowledge(
    knowledge_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """获取单条法律知识详情"""
    _ = current_user
    knowledge = await service.get_knowledge(db, knowledge_id)
    if not knowledge:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    return knowledge


@router.put("/laws/{knowledge_id}", response_model=LegalKnowledgeResponse)
async def update_knowledge(
    knowledge_id: int,
    data: LegalKnowledgeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """更新法律知识"""
    _ = current_user
    knowledge = await service.update_knowledge(db, knowledge_id, data)
    if not knowledge:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    return knowledge


@router.delete("/laws/{knowledge_id}")
async def delete_knowledge(
    knowledge_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """删除法律知识"""
    _ = current_user
    success = await service.delete_knowledge(db, knowledge_id)
    if not success:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    return {"message": "删除成功"}


@router.post("/laws/batch-delete", response_model=BatchOperationResponse)
async def batch_delete_knowledge(
    data: BatchDeleteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """批量删除法律知识"""
    _ = current_user
    success, failed = await service.batch_delete_knowledge(db, data.ids)
    return BatchOperationResponse(
        success_count=success,
        failed_count=failed,
        message=f"成功删除 {success} 条，失败 {failed} 条",
    )


@router.post("/laws/batch-import", response_model=BatchImportKnowledgeResponse)
async def batch_import_knowledge(
    data: BatchImportKnowledgeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    _ = current_user

    if data.dry_run:
        return BatchImportKnowledgeResponse(
            success_count=0,
            failed_count=0,
            message=f"校验通过：共 {len(data.items)} 条（dry_run 未写入）",
        )

    success, failed = await service.batch_import_knowledge(db, data.items)
    return BatchImportKnowledgeResponse(
        success_count=success,
        failed_count=failed,
        message=f"导入完成：成功 {success} 条，失败 {failed} 条",
    )


# === 向量化 API ===

@router.post("/laws/{knowledge_id}/vectorize")
async def vectorize_knowledge(
    knowledge_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """将单条知识向量化到向量库"""
    _ = current_user
    success = await service.vectorize_knowledge(db, knowledge_id)
    if not success:
        raise HTTPException(status_code=400, detail="向量化失败，请检查知识条目是否存在或AI服务是否配置")
    return {"message": "向量化成功"}


@router.post("/laws/batch-vectorize", response_model=BatchOperationResponse)
async def batch_vectorize(
    data: BatchVectorizeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """批量向量化知识"""
    _ = current_user
    success, failed = await service.batch_vectorize(db, data.ids)
    return BatchOperationResponse(
        success_count=success,
        failed_count=failed,
        message=f"成功向量化 {success} 条，失败 {failed} 条",
    )


@router.post("/sync-vector-store", response_model=BatchOperationResponse)
async def sync_vector_store(
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """同步所有未向量化的知识到向量库"""
    _ = current_user
    success, failed = await service.sync_all_to_vector_store(db)
    return BatchOperationResponse(
        success_count=success,
        failed_count=failed,
        message=f"同步完成：成功 {success} 条，失败 {failed} 条",
    )


# === 统计和分类 API ===

@router.get("/stats", response_model=KnowledgeStats)
async def get_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """获取知识库统计信息"""
    _ = current_user
    return await service.get_stats(db)


@router.get("/laws/distinct-categories", response_model=list[str])
async def get_distinct_law_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """获取所有分类列表"""
    _ = current_user
    return await service.get_categories(db)


# === 咨询模板 API ===

@router.post("/templates", response_model=ConsultationTemplateResponse)
async def create_template(
    data: ConsultationTemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """
    创建咨询模板
    
    - **name**: 模板名称
    - **category**: 分类
    - **questions**: 预设问题列表
    """
    _ = current_user
    template = await service.create_template(db, data)
    questions = service.parse_template_questions(template)
    return ConsultationTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        icon=template.icon,
        questions=questions,
        sort_order=template.sort_order,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.get("/templates", response_model=list[ConsultationTemplateResponse])
async def list_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    category: Annotated[str | None, Query(description="分类过滤")] = None,
    is_active: Annotated[str | None, Query(description="是否启用（true/false，为空表示不筛选）")] = None,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
):
    """获取咨询模板列表"""

    parsed_is_active: bool | None
    if is_active is None:
        parsed_is_active = True
    else:
        value = is_active.strip().lower()
        if value == "":
            parsed_is_active = None
        elif value in {"true", "1", "yes", "y"}:
            parsed_is_active = True
        elif value in {"false", "0", "no", "n"}:
            parsed_is_active = False
        else:
            raise HTTPException(status_code=422, detail="is_active 参数无效，应为 true/false")

    if parsed_is_active is not True:
        if current_user is None or not (current_user.role in {"admin", "super_admin"}):
            raise HTTPException(status_code=403, detail="需要管理员权限")

    templates = await service.list_templates(db, category, parsed_is_active)
    result: list[ConsultationTemplateResponse] = []
    for template in templates:
        questions = service.parse_template_questions(template)
        result.append(ConsultationTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            category=template.category,
            icon=template.icon,
            questions=questions,
            sort_order=template.sort_order,
            is_active=template.is_active,
            created_at=template.created_at,
            updated_at=template.updated_at,
        ))
    return result


@router.get("/templates/{template_id}", response_model=ConsultationTemplateResponse)
async def get_template(
    template_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """获取单个咨询模板"""
    _ = current_user
    template = await service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    questions = service.parse_template_questions(template)
    return ConsultationTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        icon=template.icon,
        questions=questions,
        sort_order=template.sort_order,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.put("/templates/{template_id}", response_model=ConsultationTemplateResponse)
async def update_template(
    template_id: int,
    data: ConsultationTemplateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """更新咨询模板"""
    _ = current_user
    template = await service.update_template(db, template_id, data)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    questions = service.parse_template_questions(template)
    return ConsultationTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        icon=template.icon,
        questions=questions,
        sort_order=template.sort_order,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """删除咨询模板"""
    _ = current_user
    success = await service.delete_template(db, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"message": "删除成功"}


# === 分类管理 API ===

from typing import ClassVar
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from ..models.knowledge import KnowledgeCategory


class CategoryCreate(BaseModel):
    name: str
    description: str | None = None
    parent_id: int | None = None
    icon: str = "Folder"
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_id: int | None = None
    icon: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: str | None
    parent_id: int | None
    icon: str
    sort_order: int
    is_active: bool

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
    include_inactive: bool = False,
):
    """获取所有分类"""
    _ = current_user
    query = select(KnowledgeCategory).order_by(KnowledgeCategory.sort_order)
    if not include_inactive:
        query = query.where(KnowledgeCategory.is_active == True)
    result = await db.execute(query)
    categories = result.scalars().all()
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post("/categories", response_model=CategoryResponse)
async def create_category(
    data: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """创建分类"""
    _ = current_user
    # 检查名称是否已存在
    existing = await db.execute(
        select(KnowledgeCategory).where(KnowledgeCategory.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="分类名称已存在")
    
    category = KnowledgeCategory(
        name=data.name,
        description=data.description,
        parent_id=data.parent_id,
        icon=data.icon,
        sort_order=data.sort_order,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """更新分类"""
    _ = current_user
    result = await db.execute(
        select(KnowledgeCategory).where(KnowledgeCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    if data.name is not None:
        category.name = data.name
    if data.description is not None:
        category.description = data.description
    if data.parent_id is not None:
        category.parent_id = data.parent_id
    if data.icon is not None:
        category.icon = data.icon
    if data.sort_order is not None:
        category.sort_order = data.sort_order
    if data.is_active is not None:
        category.is_active = data.is_active
    
    await db.commit()
    await db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """删除分类"""
    _ = current_user
    result = await db.execute(
        select(KnowledgeCategory).where(KnowledgeCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    await db.delete(category)
    await db.commit()
    return {"message": "删除成功"}


# === 批量导入 API ===

from fastapi import UploadFile, File
import csv
import io


class BatchImportItem(BaseModel):
    knowledge_type: str = "law"
    title: str
    article_number: str | None = None
    content: str
    summary: str | None = None
    category: str
    keywords: str | None = None
    source: str | None = None
    effective_date: str | None = None
    weight: float = 1.0
    is_active: bool = True


class BatchImportRequest(BaseModel):
    items: list[BatchImportItem]


@router.post("/laws/batch-import-legacy")
async def batch_import_knowledge_legacy(
    data: BatchImportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """
    批量导入法律知识
    
    接收JSON格式的数据列表进行批量导入
    """
    _ = current_user
    success_count = 0
    failed_items: list[dict[str, object]] = []
    
    for idx, item in enumerate(data.items):
        try:
            try:
                parsed_knowledge_type = KnowledgeType(item.knowledge_type)
            except Exception:
                raise HTTPException(status_code=422, detail="knowledge_type 参数无效")

            create_data = LegalKnowledgeCreate(
                knowledge_type=parsed_knowledge_type,
                title=item.title,
                article_number=item.article_number,
                content=item.content,
                summary=item.summary,
                category=item.category,
                keywords=item.keywords,
                source=item.source,
                effective_date=item.effective_date,
                weight=item.weight,
                is_active=item.is_active,
            )
            _ = await service.create_knowledge(db, create_data)
            success_count += 1
        except Exception as e:
            failed_items.append({"index": idx, "title": item.title, "error": str(e)})
    
    return {
        "message": f"导入完成",
        "success_count": success_count,
        "failed_count": len(failed_items),
        "failed_items": failed_items
    }


@router.post("/laws/import-csv")
async def import_csv(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    """
    从CSV文件导入法律知识
    
    CSV格式要求（首行为标题行）:
    - title: 标题（必填）
    - content: 内容（必填）
    - category: 分类（必填）
    - knowledge_type: 类型（可选，默认law）
    - article_number: 条款编号（可选）
    - summary: 摘要（可选）
    - keywords: 关键词（可选）
    - source: 来源（可选）
    - effective_date: 生效日期（可选）
    """
    _ = current_user

    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="请上传CSV文件")
    
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')  # 支持带BOM的UTF-8
    except UnicodeDecodeError:
        text = content.decode('gbk')  # 尝试GBK编码
    
    reader = csv.DictReader(io.StringIO(text))
    
    success_count = 0
    failed_items: list[dict[str, object]] = []
    
    for idx, row in enumerate(reader):
        try:
            if not row.get('title') or not row.get('content') or not row.get('category'):
                failed_items.append({"row": idx + 2, "error": "缺少必填字段(title/content/category)"})
                continue

            try:
                parsed_knowledge_type = KnowledgeType(str(row.get('knowledge_type', 'law')))
            except Exception:
                raise HTTPException(status_code=422, detail="knowledge_type 参数无效")
            
            create_data = LegalKnowledgeCreate(
                knowledge_type=parsed_knowledge_type,
                title=row['title'],
                article_number=row.get('article_number'),
                content=row['content'],
                summary=row.get('summary'),
                category=row['category'],
                keywords=row.get('keywords'),
                source=row.get('source'),
                effective_date=row.get('effective_date'),
                weight=float(row.get('weight', 1.0)),
                is_active=True,
            )
            _ = await service.create_knowledge(db, create_data)
            success_count += 1
        except Exception as e:
            failed_items.append({"row": idx + 2, "title": row.get('title', ''), "error": str(e)})
    
    return {
        "message": "CSV导入完成",
        "success_count": success_count,
        "failed_count": len(failed_items),
        "failed_items": failed_items[:20]  # 最多返回20条错误
    }
