from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IntentResult:
    intent: str
    needs_clarification: bool
    clarifying_questions: list[str]


class AiIntentClassifier:
    """Rule-based intent classifier and clarifying question generator.

    - Pure rules (no LLM)
    - Safe to run for every request
    - Output is intended to be exposed via /api/ai/chat meta fields
    """

    INTENT_PATTERNS: list[tuple[str, list[str]]] = [
        ("labor", ["工资", "加班", "劳动合同", "辞退", "社保", "工伤", "仲裁", "试用期", "离职"]),
        ("contract", ["合同", "违约", "甲方", "乙方", "定金", "赔偿", "解除合同", "履行", "收款", "付款"]),
        ("marriage", ["离婚", "结婚", "彩礼", "抚养", "夫妻", "出轨", "家暴", "财产分割", "探望权"]),
        ("property", ["房产", "买房", "卖房", "物业", "开发商", "房东", "租房", "租客", "押金", "拆迁"]),
        ("traffic", ["交通事故", "车祸", "交警", "保险", "责任认定", "赔付", "伤残", "医疗费"]),
        ("loan", ["借钱", "借款", "欠钱", "欠款", "借条", "欠条", "还款", "利息", "转账", "网贷"]),
        ("criminal", ["刑事", "犯罪", "拘留", "逮捕", "判刑", "坐牢", "诈骗", "盗窃", "故意伤害"]),
    ]

    _time_re = re.compile(r"(\d{4}年|\d{1,2}月|\d{1,2}日|\d{1,2}号|昨天|今天|前天|上周|本周|下周)")
    _amount_re = re.compile(r"(\d+(?:\.\d+)?\s*(?:万|元|块|人民币)|[一二三四五六七八九十百千万]+\s*(?:万|元))")
    _evidence_re = re.compile(r"(合同|转账|聊天记录|录音|截图|发票|借条|欠条|证据|鉴定|判决|裁定)")

    def classify(self, text: str) -> IntentResult:
        s = str(text or "").strip()
        lowered = s.lower()

        intent = "general"
        for name, keywords in self.INTENT_PATTERNS:
            for kw in keywords:
                if kw.lower() in lowered:
                    intent = name
                    break
            if intent != "general":
                break

        questions = self._build_clarifying_questions(intent, s)
        needs = len(questions) > 0
        return IntentResult(intent=intent, needs_clarification=needs, clarifying_questions=questions)

    def _build_clarifying_questions(self, intent: str, text: str) -> list[str]:
        s = str(text or "")
        questions: list[str] = []

        has_time = bool(self._time_re.search(s))
        has_amount = bool(self._amount_re.search(s))
        has_evidence = bool(self._evidence_re.search(s))

        if intent == "labor":
            if "劳动合同" not in s and "合同" not in s:
                questions.append("是否签订劳动合同？有无入职协议/工牌/考勤记录等能证明劳动关系的材料？")
            if ("辞退" in s or "离职" in s) and ("原因" not in s and "理由" not in s):
                questions.append("解除/辞退的具体原因是什么？是否收到书面通知或聊天记录？")
            if not has_amount:
                questions.append("涉及拖欠工资/补偿金的大概金额是多少？")
            if not has_time:
                questions.append("事件发生的时间节点是什么？目前进展到哪一步（在职/已离职/已仲裁）？")
            if not has_evidence:
                questions.append("你目前掌握哪些证据？例如劳动合同、工资条、转账记录、聊天记录、考勤等。")

        elif intent == "contract":
            if "合同" not in s and ("协议" not in s):
                questions.append("是否有书面合同/协议？关键条款（标的、价款、交付、违约责任）是什么？")
            if not has_amount:
                questions.append("争议金额大概是多少？是否已付款/收款？")
            if not has_time:
                questions.append("合同签订与履行时间线是怎样的？目前处于履行中还是已终止？")
            if not has_evidence:
                questions.append("是否保留了合同文本、付款凭证、往来邮件/聊天记录等证据？")

        elif intent == "marriage":
            if "孩子" in s and ("抚养" not in s and "抚养权" not in s):
                questions.append("是否有子女？孩子年龄多大？你希望争取抚养权还是探望权？")
            if "财产" not in s:
                questions.append("夫妻共同财产大致有哪些（房、车、存款、债务）？是否有婚前财产或婚后赠与？")
            if not has_time:
                questions.append("关键时间节点是什么（结婚/分居/起诉/家暴发生时间）？")
            if not has_evidence:
                questions.append("是否有相关证据（转账、聊天记录、报警回执、医院诊断、照片等）？")

        elif intent == "property":
            if "租" in s and ("租赁合同" not in s and "合同" not in s):
                questions.append("是否有租赁合同？押金/租金/期限/违约条款如何约定？")
            if not has_amount:
                questions.append("涉及的金额（房款/押金/维修费/违约金）大概是多少？")
            if not has_time:
                questions.append("事件发生的时间节点是什么？目前处于签约、交付、入住还是退租阶段？")
            if not has_evidence:
                questions.append("是否保留了合同、付款凭证、验房单、聊天记录等证据？")

        elif intent == "traffic":
            if "责任" not in s:
                questions.append("是否有交警出具的事故责任认定书？责任比例如何？")
            if "保险" not in s:
                questions.append("是否有投保交强险/商业险？保险公司是否已经介入定损？")
            if not has_time:
                questions.append("事故发生时间、地点、伤情与治疗情况如何？")
            if not has_evidence:
                questions.append("是否有现场照片/行车记录仪、病历/发票、维修清单等证据？")

        elif intent == "loan":
            if ("借条" not in s and "欠条" not in s and "合同" not in s):
                questions.append("是否有借条/欠条/借款合同？是否约定利息和还款期限？")
            if not has_amount:
                questions.append("借款金额是多少？是否分多次转账？")
            if not has_time:
                questions.append("借款发生时间与约定还款时间是什么？目前是否逾期？")
            if not has_evidence:
                questions.append("是否保留转账记录、聊天记录、催款记录等证据？")

        elif intent == "criminal":
            questions.append("该问题可能涉及刑事风险，具体案情细节非常关键。建议尽快咨询专业律师。")

        if intent == "general":
            if not has_time:
                questions.append("这件事是什么时候发生的？目前进展到什么阶段？")
            if not has_amount:
                questions.append("是否涉及金额？大概是多少？")
            if not has_evidence:
                questions.append("你目前有哪些证据材料？比如合同、转账记录、聊天记录等。")
            questions.append("你希望达成什么目标（协商/投诉/仲裁/起诉/要求赔偿等）？")

        return questions[:6]
