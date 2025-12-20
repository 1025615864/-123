"""法律文书生成API路由"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.utils.deps import get_current_user_optional
from app.utils.rate_limiter import rate_limit, RateLimitConfig

router = APIRouter(prefix="/documents", tags=["文书生成"])


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


@router.post("/generate", response_model=DocumentResponse)
@rate_limit(*RateLimitConfig.DOCUMENT_GENERATE, by_ip=True, by_user=False)
async def generate_document(
    data: DocumentGenerateRequest,
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user_optional)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """生成法律文书"""
    _ = request
    _ = current_user
    _ = db

    if len(data.facts) > 8000 or len(data.claims) > 4000 or (data.evidence and len(data.evidence) > 4000):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="输入内容过长，请缩短事实/诉求/证据描述"
        )

    if data.document_type not in DOCUMENT_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文书类型: {data.document_type}"
        )
    
    template_info = DOCUMENT_TEMPLATES[data.document_type]
    template = template_info["template"]
    
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
    content = template.format(
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
    
    return DocumentResponse(
        document_type=data.document_type,
        title=template_info["title"],
        content=content,
        created_at=datetime.now()
    )


@router.get("/types")
async def get_document_types():
    """获取支持的文书类型"""
    return [
        {"type": "complaint", "name": "民事起诉状", "description": "向法院提起民事诉讼的文书"},
        {"type": "defense", "name": "民事答辩状", "description": "被告针对原告诉讼请求的答辩文书"},
        {"type": "agreement", "name": "和解协议书", "description": "双方达成和解的协议文书"},
        {"type": "letter", "name": "律师函", "description": "以律师名义发出的法律文书"},
    ]
