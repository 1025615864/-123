from __future__ import annotations

from typing_extensions import TypedDict


class BuiltinDocumentTemplate(TypedDict):
    title: str
    description: str
    template: str


BUILTIN_DOCUMENT_TEMPLATES: dict[str, BuiltinDocumentTemplate] = {
    "complaint": {
        "title": "民事起诉状",
        "description": "向法院提起民事诉讼的文书",
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
    证据材料 {evidence_count} 份""",
    },
    "defense": {
        "title": "民事答辩状",
        "description": "被告针对原告诉讼请求的答辩文书",
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
{date}""",
    },
    "agreement": {
        "title": "和解协议书",
        "description": "双方达成和解的协议文书",
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

日期：{date}                    日期：{date}""",
    },
    "letter": {
        "title": "律师函",
        "description": "以律师名义发出的法律文书",
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
{date}""",
    },
}
