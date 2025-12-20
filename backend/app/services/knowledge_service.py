"""知识库服务"""
import json
import logging
from typing import cast

from sqlalchemy import select, func, delete, CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import LegalKnowledge, ConsultationTemplate, KnowledgeType
from app.schemas.knowledge import (
    LegalKnowledgeCreate,
    LegalKnowledgeUpdate,
    ConsultationTemplateCreate,
    ConsultationTemplateUpdate,
    TemplateQuestionItem,
    KnowledgeStats,
)

logger = logging.getLogger(__name__)


class KnowledgeService:
    """知识库服务"""
    
    # === 法律知识 CRUD ===
    
    async def create_knowledge(
        self,
        db: AsyncSession,
        data: LegalKnowledgeCreate
    ) -> LegalKnowledge:
        """创建法律知识"""
        knowledge = LegalKnowledge(
            knowledge_type=data.knowledge_type.value,
            title=data.title,
            article_number=data.article_number,
            content=data.content,
            summary=data.summary,
            category=data.category,
            keywords=data.keywords,
            source=data.source,
            effective_date=data.effective_date,
            weight=data.weight,
            is_active=data.is_active,
        )
        db.add(knowledge)
        await db.commit()
        await db.refresh(knowledge)
        return knowledge
    
    async def get_knowledge(
        self,
        db: AsyncSession,
        knowledge_id: int
    ) -> LegalKnowledge | None:
        """获取单条法律知识"""
        result = await db.execute(
            select(LegalKnowledge).where(LegalKnowledge.id == knowledge_id)
        )
        return result.scalar_one_or_none()
    
    async def list_knowledge(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        knowledge_type: str | None = None,
        category: str | None = None,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[LegalKnowledge], int]:
        """获取法律知识列表"""
        query = select(LegalKnowledge)
        count_query = select(func.count(LegalKnowledge.id))
        
        # 过滤条件
        if knowledge_type:
            query = query.where(LegalKnowledge.knowledge_type == knowledge_type)
            count_query = count_query.where(LegalKnowledge.knowledge_type == knowledge_type)
        
        if category:
            query = query.where(LegalKnowledge.category == category)
            count_query = count_query.where(LegalKnowledge.category == category)
        
        if keyword:
            search_pattern = f"%{keyword}%"
            query = query.where(
                (LegalKnowledge.title.ilike(search_pattern)) |
                (LegalKnowledge.content.ilike(search_pattern)) |
                (LegalKnowledge.keywords.ilike(search_pattern))
            )
            count_query = count_query.where(
                (LegalKnowledge.title.ilike(search_pattern)) |
                (LegalKnowledge.content.ilike(search_pattern)) |
                (LegalKnowledge.keywords.ilike(search_pattern))
            )
        
        if is_active is not None:
            query = query.where(LegalKnowledge.is_active == is_active)
            count_query = count_query.where(LegalKnowledge.is_active == is_active)
        
        # 排序和分页
        query = query.order_by(LegalKnowledge.weight.desc(), LegalKnowledge.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await db.execute(query)
        items = list(result.scalars().all())
        
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def update_knowledge(
        self,
        db: AsyncSession,
        knowledge_id: int,
        data: LegalKnowledgeUpdate
    ) -> LegalKnowledge | None:
        """更新法律知识"""
        knowledge = await self.get_knowledge(db, knowledge_id)
        if not knowledge:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        if "knowledge_type" in update_data and update_data["knowledge_type"]:
            update_data["knowledge_type"] = update_data["knowledge_type"].value
        
        for key, value in update_data.items():
            setattr(knowledge, key, value)
        
        # 内容变更时需要重新向量化
        if "content" in update_data or "title" in update_data:
            knowledge.is_vectorized = False
        
        await db.commit()
        await db.refresh(knowledge)
        return knowledge
    
    async def delete_knowledge(
        self,
        db: AsyncSession,
        knowledge_id: int
    ) -> bool:
        """删除法律知识"""
        knowledge = await self.get_knowledge(db, knowledge_id)
        if not knowledge:
            return False
        
        await db.delete(knowledge)
        await db.commit()
        return True
    
    async def batch_delete_knowledge(
        self,
        db: AsyncSession,
        ids: list[int]
    ) -> tuple[int, int]:
        """批量删除法律知识"""
        cursor_result = await db.execute(
            delete(LegalKnowledge).where(LegalKnowledge.id.in_(ids))
        )
        await db.commit()
        deleted = cast(CursorResult[tuple[()]], cursor_result).rowcount or 0
        return deleted, len(ids) - deleted
    
    # === 向量化操作 ===
    
    def _try_get_ai_assistant(self):
        try:
            from app.services.ai_assistant import get_ai_assistant

            return get_ai_assistant()
        except Exception:
            logger.exception("AI助手不可用，无法进行向量化")
            return None
    
    async def vectorize_knowledge(
        self,
        db: AsyncSession,
        knowledge_id: int
    ) -> bool:
        """将单条知识向量化到ChromaDB"""
        knowledge = await self.get_knowledge(db, knowledge_id)
        if not knowledge or knowledge.is_vectorized:
            return False
        
        try:
            assistant = self._try_get_ai_assistant()
            if assistant is None:
                return False

            kb = assistant.knowledge_base
            kb.initialize()
            
            if kb.vector_store is None:
                logger.warning("向量数据库未初始化")
                return False
            
            # 构建文档
            doc: dict[str, object] = {
                "law_name": knowledge.title,
                "article": knowledge.article_number or "",
                "content": knowledge.content,
                "source": knowledge.source or knowledge.category,
            }
            
            kb.add_law_documents([doc])
            
            knowledge.is_vectorized = True
            await db.commit()
            return True
            
        except Exception:
            logger.exception("向量化失败")
            return False
    
    async def batch_vectorize(
        self,
        db: AsyncSession,
        ids: list[int]
    ) -> tuple[int, int]:
        """批量向量化"""
        success = 0
        failed = 0
        
        for kid in ids:
            if await self.vectorize_knowledge(db, kid):
                success += 1
            else:
                failed += 1
        
        return success, failed
    
    async def sync_all_to_vector_store(self, db: AsyncSession) -> tuple[int, int]:
        """同步所有未向量化的知识到向量库"""
        result = await db.execute(
            select(LegalKnowledge).where(
                LegalKnowledge.is_active == True,
                LegalKnowledge.is_vectorized == False
            )
        )
        items = result.scalars().all()
        
        success = 0
        failed = 0
        
        for item in items:
            if await self.vectorize_knowledge(db, item.id):
                success += 1
            else:
                failed += 1
        
        return success, failed
    
    # === 统计 ===
    
    async def get_stats(self, db: AsyncSession) -> KnowledgeStats:
        """获取知识库统计"""
        # 各类型统计
        type_counts: dict[str, int] = {}
        for kt in KnowledgeType:
            result = await db.execute(
                select(func.count(LegalKnowledge.id)).where(
                    LegalKnowledge.knowledge_type == kt.value
                )
            )
            type_counts[kt.value] = result.scalar() or 0
        
        # 已向量化数量
        vectorized_result = await db.execute(
            select(func.count(LegalKnowledge.id)).where(
                LegalKnowledge.is_vectorized == True
            )
        )
        vectorized_count = vectorized_result.scalar() or 0
        
        # 分类统计
        category_result = await db.execute(
            select(
                LegalKnowledge.category,
                func.count(LegalKnowledge.id).label("count")
            ).group_by(LegalKnowledge.category)
        )
        categories = [
            {"category": row[0], "count": row[1]}
            for row in category_result.all()
        ]
        
        return KnowledgeStats(
            total_laws=type_counts.get("law", 0),
            total_cases=type_counts.get("case", 0),
            total_regulations=type_counts.get("regulation", 0),
            total_interpretations=type_counts.get("interpretation", 0),
            vectorized_count=vectorized_count,
            categories=categories,
        )
    
    # === 分类管理 ===
    
    async def get_categories(self, db: AsyncSession) -> list[str]:
        """获取所有分类"""
        result = await db.execute(
            select(LegalKnowledge.category).distinct()
        )
        return [row[0] for row in result.all()]
    
    # === 咨询模板 CRUD ===
    
    async def create_template(
        self,
        db: AsyncSession,
        data: ConsultationTemplateCreate
    ) -> ConsultationTemplate:
        """创建咨询模板"""
        template = ConsultationTemplate(
            name=data.name,
            description=data.description,
            category=data.category,
            icon=data.icon,
            questions=json.dumps([q.model_dump() for q in data.questions], ensure_ascii=False),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template
    
    async def get_template(
        self,
        db: AsyncSession,
        template_id: int
    ) -> ConsultationTemplate | None:
        """获取单个咨询模板"""
        result = await db.execute(
            select(ConsultationTemplate).where(ConsultationTemplate.id == template_id)
        )
        return result.scalar_one_or_none()
    
    async def list_templates(
        self,
        db: AsyncSession,
        category: str | None = None,
        is_active: bool | None = True
    ) -> list[ConsultationTemplate]:
        """获取咨询模板列表"""
        query = select(ConsultationTemplate)
        
        if category:
            query = query.where(ConsultationTemplate.category == category)
        
        if is_active is not None:
            query = query.where(ConsultationTemplate.is_active == is_active)
        
        query = query.order_by(ConsultationTemplate.sort_order, ConsultationTemplate.created_at)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    async def update_template(
        self,
        db: AsyncSession,
        template_id: int,
        data: ConsultationTemplateUpdate
    ) -> ConsultationTemplate | None:
        """更新咨询模板"""
        template = await self.get_template(db, template_id)
        if not template:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        
        if "questions" in update_data and update_data["questions"]:
            update_data["questions"] = json.dumps(
                [q.model_dump() if hasattr(q, 'model_dump') else q for q in update_data["questions"]],
                ensure_ascii=False
            )
        
        for key, value in update_data.items():
            setattr(template, key, value)
        
        await db.commit()
        await db.refresh(template)
        return template
    
    async def delete_template(
        self,
        db: AsyncSession,
        template_id: int
    ) -> bool:
        """删除咨询模板"""
        template = await self.get_template(db, template_id)
        if not template:
            return False
        
        await db.delete(template)
        await db.commit()
        return True
    
    def parse_template_questions(self, template: ConsultationTemplate) -> list[TemplateQuestionItem]:
        """解析模板问题列表"""
        try:
            questions_data = json.loads(template.questions)
            return [TemplateQuestionItem(**q) for q in questions_data]
        except Exception:
            return []


# 单例
_knowledge_service: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    """获取知识库服务实例"""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
