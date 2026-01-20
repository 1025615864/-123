import pytest

from app.utils.validators import (
    InputValidator,
    sanitize_html,
    validate_email,
    validate_id_card,
    validate_password_strength,
    validate_phone,
    validate_url,
    validate_username,
)


def test_validate_phone() -> None:
    assert validate_phone("13800138000") is True
    assert validate_phone("19912345678") is True
    assert validate_phone("123") is False
    assert validate_phone("23800138000") is False


def test_validate_email() -> None:
    assert validate_email("a@b.com") is True
    assert validate_email("a.b+1@sub.example.co") is True
    assert validate_email("not-an-email") is False
    assert validate_email("a@b") is False


def test_validate_url() -> None:
    assert validate_url("https://example.com/a?b=c") is True
    assert validate_url("http://127.0.0.1:8000/") is True
    assert validate_url("ftp://example.com") is False
    assert validate_url("javascript:alert(1)") is False


def test_validate_id_card() -> None:
    assert validate_id_card("11010519491231002X") is True
    assert validate_id_card("11010519491231002x") is True
    assert validate_id_card("11010519491231002A") is False
    assert validate_id_card("abc") is False


def test_validate_password_strength() -> None:
    ok, msg = validate_password_strength("Abcdef12")
    assert ok is True
    assert msg

    ok, _ = validate_password_strength("short1A")
    assert ok is False

    ok, _ = validate_password_strength("A" * 51)
    assert ok is False

    ok, _ = validate_password_strength("abcdef12")
    assert ok is False

    ok, _ = validate_password_strength("ABCDEF12")
    assert ok is False

    ok, _ = validate_password_strength("Abcdefgh")
    assert ok is False


def test_validate_username() -> None:
    ok, _ = validate_username("a")
    assert ok is False

    ok, _ = validate_username("a" * 21)
    assert ok is False

    ok, _ = validate_username("bad-name")
    assert ok is False

    ok, _ = validate_username("张三_abc123")
    assert ok is True


def test_sanitize_html() -> None:
    assert sanitize_html("<b>hi</b>") == "hi"
    assert sanitize_html("hi & <") == "hi &amp; &lt;"


def test_input_validator_collects_errors() -> None:
    v = InputValidator()
    v.required(None, "name")
    v.min_length("a", 2, "name")
    v.max_length("abc", 2, "name")
    v.validate("bad", validate_email, "email invalid")

    assert v.is_valid() is False
    errors = v.get_errors()
    assert len(errors) == 4
    assert v.get_first_error() == errors[0]


def test_input_validator_reset() -> None:
    v = InputValidator()
    v.required(None, "name")
    assert v.is_valid() is False

    v.reset()
    assert v.is_valid() is True


def test_input_validator_required_trims_spaces() -> None:
    v = InputValidator()
    v.required("   ", "name")
    assert v.is_valid() is False


@pytest.mark.parametrize(
    "value,validator,expected",
    [
        ("13800138000", validate_phone, True),
        ("not-an-email", validate_email, False),
    ],
)
def test_input_validator_validate(value: str, validator, expected: bool) -> None:
    v = InputValidator()
    v.validate(value, validator, "bad")
    assert v.is_valid() is expected
