"""知识库管理API路由"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models.knowledge import LegalKnowledge, ConsultationTemplate
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
)
from ..services.knowledge_service import get_knowledge_service, KnowledgeService
from ..utils.deps import require_admin, get_current_user_optional

import json
import logging
from pathlib import Path

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])

logger = logging.getLogger(__name__)
settings = get_settings()


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


# === 向量化 API ===


class VectorStoreStatusResponse(BaseModel):
    openai_api_key_configured: bool
    chroma_persist_dir: str
    persist_dir_exists: bool
    initialized: bool
    embeddings_ready: bool
    vector_store_ready: bool
    collection_name: str | None = None
    collection_count: int | None = None
    error: str | None = None


@router.get("/vector-store/status", response_model=VectorStoreStatusResponse)
async def get_vector_store_status(
    current_user: Annotated[User, Depends(require_admin)],
):
    _ = current_user

    persist_dir = str(getattr(settings, "chroma_persist_dir", "") or "")
    persist_dir_exists = bool(persist_dir) and Path(persist_dir).exists()

    out: dict[str, object] = {
        "openai_api_key_configured": bool(settings.openai_api_key),
        "chroma_persist_dir": persist_dir,
        "persist_dir_exists": bool(persist_dir_exists),
        "initialized": False,
        "embeddings_ready": False,
        "vector_store_ready": False,
        "collection_name": None,
        "collection_count": None,
        "error": None,
    }

    if not bool(settings.openai_api_key):
        return out

    try:
        from ..services.ai_assistant import get_ai_assistant

        assistant = get_ai_assistant()
        kb = assistant.knowledge_base
        kb.initialize()

        out["initialized"] = bool(getattr(kb, "_initialized", False))
        out["embeddings_ready"] = kb.embeddings is not None
        out["vector_store_ready"] = kb.vector_store is not None

        if kb.vector_store is not None:
            out["collection_name"] = "legal_knowledge"
            coll = getattr(kb.vector_store, "_collection", None)
            if coll is not None:
                count_fn = getattr(coll, "count", None)
                if callable(count_fn):
                    try:
                        out["collection_count"] = int(count_fn())
                    except Exception:
                        out["collection_count"] = None
    except Exception as e:
        logger.exception("get_vector_store_status_failed")
        out["error"] = f"{type(e).__name__}: {str(e)}"

    return out

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


@router.post("/templates/import-seed")
async def import_seed_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[KnowledgeService, Depends(get_knowledge_service)],
    current_user: Annotated[User, Depends(require_admin)],
):
    _ = current_user

    seeds: list[dict[str, object]] = [
        {
            "name": "劳动纠纷咨询",
            "description": "适用于被辞退、拖欠工资、社保争议等场景",
            "category": "劳动纠纷",
            "icon": "Briefcase",
            "questions": [
                {"question": "我被公司辞退/劝退了，是否合法？", "hint": "说明原因、入职时间、是否签合同"},
                {"question": "公司拖欠工资/加班费怎么办？", "hint": "说明金额、证据（工资条/转账/考勤）"},
                {"question": "公司不给交社保怎么办？", "hint": "说明缴纳情况、是否有劳动关系证明"},
            ],
            "sort_order": 0,
            "is_active": True,
        },
        {
            "name": "婚姻家庭咨询",
            "description": "适用于离婚、抚养权、财产分割等场景",
            "category": "婚姻家庭",
            "icon": "Heart",
            "questions": [
                {"question": "我想离婚，需要准备什么材料？", "hint": "协议离婚/诉讼离婚"},
                {"question": "孩子抚养权一般怎么判？", "hint": "孩子年龄、双方抚养条件"},
                {"question": "房子/存款/债务离婚怎么分？", "hint": "是否婚前财产、共同还贷情况"},
            ],
            "sort_order": 1,
            "is_active": True,
        },
        {
            "name": "合同纠纷咨询",
            "description": "适用于买卖合同、服务合同、定金违约等场景",
            "category": "合同纠纷",
            "icon": "FileText",
            "questions": [
                {"question": "对方不履行合同/违约了怎么办？", "hint": "合同条款、违约行为、损失"},
                {"question": "定金能退吗？违约金怎么计算？", "hint": "支付方式、约定条款"},
                {"question": "没有签书面合同，微信聊天算证据吗？", "hint": "聊天记录、付款凭证"},
            ],
            "sort_order": 2,
            "is_active": True,
        },
        {
            "name": "交通事故咨询",
            "description": "适用于责任认定、赔偿项目、保险理赔等场景",
            "category": "交通事故",
            "icon": "Car",
            "questions": [
                {"question": "交通事故责任怎么认定？", "hint": "是否有责任认定书、现场情况"},
                {"question": "赔偿包含哪些项目？", "hint": "医疗费、误工费、护理费等"},
                {"question": "对方不赔钱怎么办？", "hint": "是否有保险、证据材料"},
            ],
            "sort_order": 3,
            "is_active": True,
        },
        {
            "name": "消费维权咨询",
            "description": "适用于退货退款、虚假宣传、质量问题等场景",
            "category": "消费维权",
            "icon": "ShoppingCart",
            "questions": [
                {"question": "买到假货/质量问题如何维权？", "hint": "订单、聊天记录、检测报告"},
                {"question": "商家拒绝退货退款怎么办？", "hint": "是否在7天无理由期限内"},
                {"question": "虚假宣传能否要求赔偿？", "hint": "宣传页面截图、承诺内容"},
            ],
            "sort_order": 4,
            "is_active": True,
        },
    ]

    success_count = 0
    skipped_count = 0
    failed_items: list[dict[str, object]] = []

    for seed in seeds:
        try:
            name = str(seed.get("name") or "").strip()
            category = str(seed.get("category") or "").strip()
            if not name or not category:
                raise ValueError("missing fields")

            existing = await db.execute(
                select(ConsultationTemplate).where(
                    ConsultationTemplate.name == name,
                    ConsultationTemplate.category == category,
                )
            )
            if existing.scalar_one_or_none() is not None:
                skipped_count += 1
                continue

            data = ConsultationTemplateCreate.model_validate(seed)
            _ = await service.create_template(db, data)
            success_count += 1
        except Exception as e:
            failed_items.append({"name": str(seed.get("name") or ""), "error": str(e)})

    return {
        "success_count": success_count,
        "skipped_count": skipped_count,
        "failed_count": len(failed_items),
        "failed_items": failed_items[:20],
        "message": f"导入完成：新增 {success_count} 条，跳过 {skipped_count} 条，失败 {len(failed_items)} 条",
    }


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


@router.post("/laws/import-seed")
async def import_seed_laws(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    _ = current_user
    base_dir = Path(__file__).resolve().parents[2]
    laws_dir = base_dir / "knowledge_base" / "laws"
    if not laws_dir.exists() or not laws_dir.is_dir():
        raise HTTPException(status_code=404, detail="knowledge_base/laws 目录不存在")

    category_map: dict[str, str] = {
        "civil_code": "民法",
        "contract_law": "合同法",
        "labor_law": "劳动法",
        "marriage_law": "婚姻家庭",
        "consumer_law": "消费者权益",
    }

    success_count = 0
    skipped_count = 0
    failed_items: list[dict[str, object]] = []

    for p in sorted(laws_dir.glob("*.json")):
        stem = str(p.stem)
        category = category_map.get(stem, "其他")

        try:
            raw = p.read_text(encoding="utf-8")
            items = json.loads(raw)
            if not isinstance(items, list):
                raise ValueError("invalid json")
        except Exception as e:
            failed_items.append({"file": p.name, "error": str(e)})
            continue

        for item in items:
            try:
                if not isinstance(item, dict):
                    raise ValueError("invalid item")
                title = str(item.get("law_name") or "").strip()
                article_number = str(item.get("article") or "").strip() or None
                content = str(item.get("content") or "").strip()
                if not title or not content:
                    raise ValueError("missing fields")

                existing = await db.execute(
                    select(LegalKnowledge).where(
                        LegalKnowledge.knowledge_type == KnowledgeType.LAW.value,
                        LegalKnowledge.title == title,
                        LegalKnowledge.article_number == article_number,
                        LegalKnowledge.content == content,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    skipped_count += 1
                    continue

                knowledge = LegalKnowledge(
                    knowledge_type=KnowledgeType.LAW.value,
                    title=title,
                    article_number=article_number,
                    content=content,
                    summary=None,
                    category=category,
                    keywords=None,
                    source=p.name,
                    effective_date=None,
                    weight=1.0,
                    is_active=True,
                    is_vectorized=False,
                    vector_id=None,
                )
                db.add(knowledge)
                success_count += 1
            except Exception as e:
                failed_items.append(
                    {
                        "file": p.name,
                        "title": str(item.get("law_name") if isinstance(item, dict) else ""),
                        "error": str(e),
                    }
                )

    await db.commit()
    return {
        "success_count": success_count,
        "skipped_count": skipped_count,
        "failed_count": len(failed_items),
        "failed_items": failed_items[:20],
        "message": f"导入完成：新增 {success_count} 条，跳过 {skipped_count} 条，失败 {len(failed_items)} 条",
    }


@router.post("/laws/batch-import")
async def batch_import_knowledge(
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
