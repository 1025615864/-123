from __future__ import annotations

from app.services.ai_intent import AiIntentClassifier


def test_intent_criminal_has_fixed_question() -> None:
    c = AiIntentClassifier()
    out = c.classify("我因为诈骗被拘留")
    assert out.intent == "criminal"
    assert out.needs_clarification is True
    assert len(out.clarifying_questions) == 1
    assert "刑事风险" in out.clarifying_questions[0]


def test_intent_general_has_default_questions_and_cap() -> None:
    c = AiIntentClassifier()
    out = c.classify("你好")
    assert out.intent == "general"
    assert out.needs_clarification is True
    assert 1 <= len(out.clarifying_questions) <= 6
    assert any("希望达成什么目标" in q for q in out.clarifying_questions)


def test_intent_labor_questions_missing_fields() -> None:
    c = AiIntentClassifier()
    out = c.classify("公司拖欠工资，我想仲裁")
    assert out.intent == "labor"
    assert out.needs_clarification is True
    assert any("金额" in q for q in out.clarifying_questions)
    assert any("时间" in q for q in out.clarifying_questions)


def test_intent_loan_no_questions_when_has_time_amount_evidence() -> None:
    c = AiIntentClassifier()
    out = c.classify("2024年借款1万元，有借条和转账记录，现在逾期")
    assert out.intent == "loan"
    assert out.needs_clarification is False
    assert out.clarifying_questions == []


def test_intent_contract_detects_contract_intent() -> None:
    c = AiIntentClassifier()
    out = c.classify("合同违约，定金能退吗")
    assert out.intent == "contract"


def test_intent_marriage_questions() -> None:
    c = AiIntentClassifier()
    out = c.classify("离婚有孩子，想探望")
    assert out.intent == "marriage"
    assert out.needs_clarification is True
    assert any("子女" in q or "孩子" in q for q in out.clarifying_questions)
    assert any("财产" in q for q in out.clarifying_questions)


def test_intent_property_rent_questions() -> None:
    c = AiIntentClassifier()
    out = c.classify("租房押金不退")
    assert out.intent == "property"
    assert out.needs_clarification is True
    assert any("租赁合同" in q for q in out.clarifying_questions)


def test_intent_traffic_questions() -> None:
    c = AiIntentClassifier()
    out = c.classify("交通事故对方全责，但保险不赔")
    assert out.intent == "traffic"
    assert out.needs_clarification is True
    assert any("责任认定" in q for q in out.clarifying_questions)


def test_intent_general_no_questions_when_has_time_amount_evidence_and_goal() -> None:
    c = AiIntentClassifier()
    out = c.classify("2024年1月发生纠纷，金额1000元，有聊天记录")
    assert out.intent == "general"
    assert out.needs_clarification is True
    assert len(out.clarifying_questions) == 1
    assert "希望达成什么目标" in out.clarifying_questions[0]
