from __future__ import annotations

import types

import pytest

import app.services.sherpa_asr_service as mod


def test_normalize_mode() -> None:
    assert mod._normalize_mode("local") == "local"
    assert mod._normalize_mode("REMOTE") == "remote"
    assert mod._normalize_mode("off") == "off"
    assert mod._normalize_mode("bad") == "off"


def test_get_setting_fallback() -> None:
    s = types.SimpleNamespace(a=1)
    assert mod._get_setting(s, "a", 0) == 1
    assert mod._get_setting(s, "missing", 2) == 2


def test_sherpa_is_ready_disabled() -> None:
    s = types.SimpleNamespace(sherpa_asr_enabled=False)
    assert mod.sherpa_is_ready(s) is False


def test_sherpa_is_ready_mode_off() -> None:
    s = types.SimpleNamespace(sherpa_asr_enabled=True, sherpa_asr_mode="off")
    assert mod.sherpa_is_ready(s) is False


def test_sherpa_is_ready_remote_requires_url() -> None:
    s = types.SimpleNamespace(sherpa_asr_enabled=True, sherpa_asr_mode="remote", sherpa_asr_remote_url="")
    assert mod.sherpa_is_ready(s) is False
    s2 = types.SimpleNamespace(sherpa_asr_enabled=True, sherpa_asr_mode="remote", sherpa_asr_remote_url="http://x")
    assert mod.sherpa_is_ready(s2) is True


def test_sherpa_is_ready_local_requires_deps(monkeypatch) -> None:
    s = types.SimpleNamespace(sherpa_asr_enabled=True, sherpa_asr_mode="local")
    monkeypatch.setattr(mod, "np", None, raising=True)
    assert mod.sherpa_is_ready(s) is False

    monkeypatch.setattr(mod, "np", object(), raising=True)
    monkeypatch.setattr(mod, "sherpa_onnx", None, raising=True)
    assert mod.sherpa_is_ready(s) is False


def test_sherpa_is_ready_local_wenet_and_whisper(monkeypatch) -> None:
    monkeypatch.setattr(mod, "np", object(), raising=True)
    monkeypatch.setattr(mod, "sherpa_onnx", object(), raising=True)

    def exists(_p: str) -> bool:
        return True

    monkeypatch.setattr(mod.os.path, "exists", exists, raising=True)

    s_wenet = types.SimpleNamespace(
        sherpa_asr_enabled=True,
        sherpa_asr_mode="local",
        sherpa_onnx_tokens="/t",
        sherpa_onnx_wenet_ctc_model="/m",
        sherpa_onnx_whisper_encoder="",
        sherpa_onnx_whisper_decoder="",
    )
    assert mod.sherpa_is_ready(s_wenet) is True

    s_whisper = types.SimpleNamespace(
        sherpa_asr_enabled=True,
        sherpa_asr_mode="local",
        sherpa_onnx_tokens="/t",
        sherpa_onnx_wenet_ctc_model="",
        sherpa_onnx_whisper_encoder="/e",
        sherpa_onnx_whisper_decoder="/d",
    )
    assert mod.sherpa_is_ready(s_whisper) is True


def test_ffmpeg_available(monkeypatch) -> None:
    class CP:
        returncode = 0

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: CP(), raising=True)
    assert mod._ffmpeg_available() is True

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(mod.subprocess, "run", boom, raising=True)
    assert mod._ffmpeg_available() is False


def test_convert_with_ffmpeg_requires_available(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_ffmpeg_available", lambda: False, raising=True)
    with pytest.raises(RuntimeError):
        mod._convert_with_ffmpeg_to_wav_16k_mono(b"x", suffix=".wav")


def test_audio_to_float32_paths(monkeypatch) -> None:
    calls = {"read": 0, "conv": 0}

    def read_ok(_b: bytes):
        calls["read"] += 1
        return ("samples", 16000)

    monkeypatch.setattr(mod, "_read_wav_bytes", read_ok, raising=True)
    out = mod._audio_to_float32_16k(b"x", "a.wav")
    assert out == ("samples", 16000)

    def read_sr(_b: bytes):
        calls["read"] += 1
        if calls["read"] == 2:
            return ("samples2", 8000)
        return ("samples3", 16000)

    def conv(_c: bytes, suffix: str):
        calls["conv"] += 1
        return b"wav"

    monkeypatch.setattr(mod, "_read_wav_bytes", read_sr, raising=True)
    monkeypatch.setattr(mod, "_convert_with_ffmpeg_to_wav_16k_mono", conv, raising=True)
    out2 = mod._audio_to_float32_16k(b"x", "a.wav")
    assert out2 == ("samples3", 16000)
    assert calls["conv"] >= 1

    def read_raise(_b: bytes):
        raise ValueError("bad")

    calls["conv"] = 0

    monkeypatch.setattr(mod, "_read_wav_bytes", read_raise, raising=True)

    def read_after(_b: bytes):
        return ("samples4", 16000)

    monkeypatch.setattr(mod, "_convert_with_ffmpeg_to_wav_16k_mono", lambda *a, **k: b"wav", raising=True)
    monkeypatch.setattr(mod, "_read_wav_bytes", lambda b: ("samples4", 16000) if b == b"wav" else (_ for _ in ()).throw(ValueError()), raising=True)
    out3 = mod._audio_to_float32_16k(b"x", "a.bin")
    assert out3 == ("samples4", 16000)


def test_local_singleton_caches_by_fingerprint(monkeypatch) -> None:
    cls = mod._SherpaLocalSingleton
    cls._recognizer = "R"
    cls._fingerprint = ("wenet_ctc", "/t", "/m")

    s = types.SimpleNamespace(
        sherpa_onnx_tokens="/t",
        sherpa_onnx_wenet_ctc_model="/m",
        sherpa_onnx_whisper_encoder="",
        sherpa_onnx_whisper_decoder="",
    )

    monkeypatch.setattr(cls, "_build_recognizer", classmethod(lambda _c, _s: (_ for _ in ()).throw(RuntimeError("should_not"))), raising=True)
    assert cls.get_recognizer(s) == "R"


def test_local_singleton_rebuilds_when_fingerprint_changes(monkeypatch) -> None:
    cls = mod._SherpaLocalSingleton
    cls._recognizer = "R"
    cls._fingerprint = ("wenet_ctc", "/t", "/m")

    s = types.SimpleNamespace(
        sherpa_onnx_tokens="/t2",
        sherpa_onnx_wenet_ctc_model="/m2",
        sherpa_onnx_whisper_encoder="",
        sherpa_onnx_whisper_decoder="",
    )

    monkeypatch.setattr(cls, "_build_recognizer", classmethod(lambda _c, _s: "R2"), raising=True)
    assert cls.get_recognizer(s) == "R2"
