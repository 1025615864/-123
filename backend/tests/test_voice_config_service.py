from __future__ import annotations

import types

import pytest

from app.models.system import SystemConfig
from app.services import voice_config_service as svc


def test_parse_bool() -> None:
    assert svc._parse_bool(None, False) is False
    assert svc._parse_bool(None, True) is True
    assert svc._parse_bool(True, False) is True
    assert svc._parse_bool(0, True) is False
    assert svc._parse_bool(1, False) is True
    assert svc._parse_bool("yes", False) is True
    assert svc._parse_bool("0", True) is False


def test_parse_int() -> None:
    assert svc._parse_int(None, 7) == 7
    assert svc._parse_int(True, 7) == 7
    assert svc._parse_int(3, 7) == 3
    assert svc._parse_int(3.2, 7) == 3
    assert svc._parse_int(" 4 ", 7) == 4
    assert svc._parse_int("", 7) == 7
    assert svc._parse_int("bad", 7) == 7


def test_settings_overlay() -> None:
    base = types.SimpleNamespace(a=1, b=2)
    o = svc._SettingsOverlay(base, {"b": 3})
    assert o.a == 1
    assert o.b == 3


@pytest.mark.asyncio
async def test_load_voice_config_overrides_filters_keys(test_session) -> None:
    test_session.add(SystemConfig(key="SHERPA_ASR_ENABLED", value="1"))
    test_session.add(SystemConfig(key="OTHER_KEY", value="x"))
    await test_session.commit()

    out = await svc.load_voice_config_overrides(test_session)
    assert out == {"SHERPA_ASR_ENABLED": "1"}


@pytest.mark.asyncio
async def test_load_voice_config_overrides_skips_empty_key() -> None:
    class DummyRes:
        def all(self):
            return [(None, "x"), ("SHERPA_ASR_ENABLED", "1")]

    class DummyDb:
        async def execute(self, _q):
            return DummyRes()

    out = await svc.load_voice_config_overrides(DummyDb())  # type: ignore[arg-type]
    assert out == {"SHERPA_ASR_ENABLED": "1"}


@pytest.mark.asyncio
async def test_get_effective_voice_settings_force_disabled_returns_base(test_session) -> None:
    base = types.SimpleNamespace(
        voice_transcribe_force_enabled=False,
        voice_transcribe_provider="auto",
        sherpa_asr_enabled=False,
        sherpa_asr_mode="off",
        sherpa_onnx_num_threads=1,
        sherpa_onnx_debug=False,
        sherpa_onnx_sample_rate=16000,
        sherpa_onnx_feature_dim=80,
    )

    settings, overrides, enabled = await svc.get_effective_voice_settings(test_session, base)
    assert settings is base
    assert overrides == {}
    assert enabled is False


@pytest.mark.asyncio
async def test_get_effective_voice_settings_force_enabled_merges_and_normalizes(test_session) -> None:
    base = types.SimpleNamespace(
        voice_transcribe_force_enabled=False,
        voice_transcribe_provider="auto",
        sherpa_asr_enabled=False,
        sherpa_asr_mode="off",
        sherpa_asr_remote_url="",
        sherpa_onnx_num_threads=1,
        sherpa_onnx_debug=False,
        sherpa_onnx_sample_rate=16000,
        sherpa_onnx_feature_dim=80,
    )

    test_session.add_all(
        [
            SystemConfig(key="VOICE_TRANSCRIBE_FORCE_ENABLED", value="1"),
            SystemConfig(key="VOICE_TRANSCRIBE_PROVIDER", value="OpenAI"),
            SystemConfig(key="SHERPA_ASR_ENABLED", value="true"),
            SystemConfig(key="SHERPA_ASR_MODE", value="REMOTE"),
            SystemConfig(key="SHERPA_ONNX_NUM_THREADS", value="4"),
            SystemConfig(key="SHERPA_ONNX_DEBUG", value="1"),
            SystemConfig(key="SHERPA_ONNX_SAMPLE_RATE", value="8000"),
            SystemConfig(key="SHERPA_ONNX_FEATURE_DIM", value="40"),
        ]
    )
    await test_session.commit()

    settings, overrides, enabled = await svc.get_effective_voice_settings(test_session, base)
    assert enabled is True
    assert overrides.get("VOICE_TRANSCRIBE_PROVIDER") == "OpenAI"

    assert settings.voice_transcribe_provider == "openai"
    assert settings.sherpa_asr_enabled is True
    assert settings.sherpa_asr_mode == "remote"
    assert settings.sherpa_onnx_num_threads == 4
    assert settings.sherpa_onnx_debug is True
    assert settings.sherpa_onnx_sample_rate == 8000
    assert settings.sherpa_onnx_feature_dim == 40


@pytest.mark.asyncio
async def test_get_effective_voice_settings_invalid_provider_and_mode_fallback(test_session) -> None:
    base = types.SimpleNamespace(
        voice_transcribe_force_enabled=False,
        voice_transcribe_provider="openai",
        sherpa_asr_enabled=False,
        sherpa_asr_mode="local",
    )

    test_session.add_all(
        [
            SystemConfig(key="VOICE_TRANSCRIBE_FORCE_ENABLED", value="1"),
            SystemConfig(key="VOICE_TRANSCRIBE_PROVIDER", value="BAD"),
            SystemConfig(key="SHERPA_ASR_MODE", value="BAD"),
        ]
    )
    await test_session.commit()

    settings, overrides, enabled = await svc.get_effective_voice_settings(test_session, base)
    assert enabled is True
    assert settings.voice_transcribe_provider == "auto"
    assert settings.sherpa_asr_mode == "off"


@pytest.mark.asyncio
async def test_get_effective_voice_settings_env_force_enabled_blank_override_ignored(test_session, monkeypatch) -> None:
    base = types.SimpleNamespace(
        voice_transcribe_force_enabled=False,
        voice_transcribe_provider="openai",
        sherpa_asr_mode="off",
    )

    monkeypatch.setenv("VOICE_TRANSCRIBE_FORCE_ENABLED", "1")
    test_session.add(SystemConfig(key="VOICE_TRANSCRIBE_PROVIDER", value="  "))
    await test_session.commit()

    settings, overrides, enabled = await svc.get_effective_voice_settings(test_session, base)
    assert enabled is True
    assert "VOICE_TRANSCRIBE_PROVIDER" in overrides
    assert settings.voice_transcribe_provider == "openai"
