import pytest

import app.utils.content_filter as mod


@pytest.fixture()
def fresh_filter(monkeypatch: pytest.MonkeyPatch) -> mod.ContentFilter:
    cf = mod.ContentFilter(custom_words=["bad"], ad_threshold=2, check_url=True, check_phone=True)
    monkeypatch.setattr(mod, "content_filter", cf)
    return cf


def test_check_content_empty_passes(fresh_filter: mod.ContentFilter) -> None:
    ok, reason, matched = fresh_filter.check_content("")
    assert ok is True
    assert reason == ""
    assert matched == []


def test_check_content_sensitive_rejects(fresh_filter: mod.ContentFilter) -> None:
    ok, reason, matched = fresh_filter.check_content("this is BAD text")
    assert ok is False
    assert reason
    assert matched


def test_check_content_ad_threshold_rejects(fresh_filter: mod.ContentFilter) -> None:
    fresh_filter.apply_config(ad_words=["free", "click"], ad_threshold=2)
    ok, reason, matched = fresh_filter.check_content("FREE stuff, CLICK now")
    assert ok is False
    assert reason
    assert set(matched) == {"free", "click"}


def test_filter_content_replaces_case_insensitive(fresh_filter: mod.ContentFilter) -> None:
    fresh_filter.apply_config(sensitive_words=["bad"], ad_words=["click"], ad_threshold=2)
    out = fresh_filter.filter_content("BAD and Click")
    assert "***" in out


def test_get_risk_level_safe_warning_danger(fresh_filter: mod.ContentFilter) -> None:
    fresh_filter.apply_config(sensitive_words=["a", "b", "c"], ad_words=[])

    assert fresh_filter.get_risk_level("hello") == "safe"
    assert fresh_filter.get_risk_level("contains a") == "warning"
    assert fresh_filter.get_risk_level("a b c") == "danger"


def test_apply_content_filter_config_updates_global(monkeypatch: pytest.MonkeyPatch) -> None:
    cf = mod.ContentFilter(custom_words=[], ad_threshold=2, check_url=True, check_phone=True)
    monkeypatch.setattr(mod, "content_filter", cf)

    mod.apply_content_filter_config(sensitive_words=["x"], ad_words=["y"], ad_words_threshold=1, check_url=False, check_phone=False)
    assert "x" in cf.sensitive_words
    assert "y" in cf.ad_words
    assert cf.ad_threshold == 1
    assert cf.check_url is False
    assert cf.check_phone is False


def test_check_post_content_allows_ad_but_blocks_sensitive(fresh_filter: mod.ContentFilter) -> None:
    fresh_filter.apply_config(sensitive_words=["bad"], ad_words=["free", "click"], ad_threshold=2)

    ok, msg = mod.check_post_content("free click", "content")
    assert ok is True
    assert msg == ""

    ok2, msg2 = mod.check_post_content("bad", "content")
    assert ok2 is False
    assert msg2

    ok3, msg3 = mod.check_post_content("title", "bad")
    assert ok3 is False
    assert msg3


def test_check_comment_content_blocks_sensitive_only(fresh_filter: mod.ContentFilter) -> None:
    fresh_filter.apply_config(sensitive_words=["bad"], ad_words=["free", "click"], ad_threshold=2)

    ok, msg = mod.check_comment_content("bad")
    assert ok is False
    assert msg

    ok2, msg2 = mod.check_comment_content("free click")
    assert ok2 is True
    assert msg2 == ""


def test_needs_review_paths(fresh_filter: mod.ContentFilter) -> None:
    fresh_filter.apply_config(sensitive_words=["bad"], ad_words=[], check_url=True, check_phone=True)

    ok, reason = mod.needs_review("bad")
    assert ok is True
    assert reason

    fresh_filter.apply_config(sensitive_words=["a", "b", "c"], ad_words=[], check_url=False, check_phone=False)
    ok2, reason2 = mod.needs_review("a b c")
    assert ok2 is True
    assert reason2

    fresh_filter.apply_config(sensitive_words=[], ad_words=[], check_url=True, check_phone=False)
    ok3, reason3 = mod.needs_review("see https://example.com")
    assert ok3 is True
    assert reason3

    fresh_filter.apply_config(sensitive_words=[], ad_words=[], check_url=False, check_phone=True)
    ok4, reason4 = mod.needs_review("my phone 13800138000")
    assert ok4 is True
    assert reason4

    fresh_filter.apply_config(sensitive_words=[], ad_words=[], check_url=False, check_phone=False)
    ok5, reason5 = mod.needs_review("clean")
    assert ok5 is False
    assert reason5 == ""


def test_add_remove_and_list_words(fresh_filter: mod.ContentFilter) -> None:
    mod.add_sensitive_word("s1")
    assert "s1" in mod.get_all_sensitive_words()

    mod.remove_sensitive_word("s1")
    assert "s1" not in mod.get_all_sensitive_words()

    mod.add_ad_word("a1")
    assert "a1" in mod.get_all_ad_words()

    mod.remove_ad_word("a1")
    assert "a1" not in mod.get_all_ad_words()
