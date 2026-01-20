from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.document import (
    DocumentDetail,
    DocumentGenerateRequest,
    DocumentItem,
    DocumentListResponse,
    DocumentResponse,
    DocumentSaveRequest,
)


def test_document_generate_request_ok() -> None:
    r = DocumentGenerateRequest(
        document_type="a",
        case_type="b",
        plaintiff_name="p",
        defendant_name="d",
        facts="f",
        claims="c",
        evidence=None,
    )
    assert r.document_type == "a"


def test_document_generate_request_facts_too_long() -> None:
    with pytest.raises(ValidationError):
        DocumentGenerateRequest(
            document_type="a",
            case_type="b",
            plaintiff_name="p",
            defendant_name="d",
            facts="x" * 9000,
            claims="c",
            evidence=None,
        )


def test_document_save_request_ok() -> None:
    r = DocumentSaveRequest(document_type="a", title="t", content="c", payload={"k": 1})
    assert r.payload == {"k": 1}


def test_document_response_ok() -> None:
    now = datetime.now(timezone.utc)
    r = DocumentResponse(document_type="a", title="t", content="c", created_at=now)
    assert r.created_at == now


def test_document_item_from_attributes() -> None:
    class Obj:
        id = 1
        document_type = "a"
        title = "t"
        created_at = datetime.now(timezone.utc)

    item = DocumentItem.model_validate(Obj())
    assert item.id == 1


def test_document_detail_from_attributes() -> None:
    class Obj:
        id = 1
        user_id = 2
        document_type = "a"
        title = "t"
        content = "c"
        payload_json = None
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

    detail = DocumentDetail.model_validate(Obj())
    assert detail.user_id == 2


def test_document_list_response_ok() -> None:
    now = datetime.now(timezone.utc)
    items = [DocumentItem(id=1, document_type="a", title="t", created_at=now)]
    r = DocumentListResponse(items=items, total=1)
    assert r.total == 1
