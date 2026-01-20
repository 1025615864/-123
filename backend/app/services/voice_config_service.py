import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


VOICE_CONFIG_KEYS: set[str] = {
    "VOICE_TRANSCRIBE_FORCE_ENABLED",
    "VOICE_TRANSCRIBE_PROVIDER",
    "SHERPA_ASR_ENABLED",
    "SHERPA_ASR_MODE",
    "SHERPA_ASR_REMOTE_URL",
    "SHERPA_ONNX_TOKENS",
    "SHERPA_ONNX_WENET_CTC_MODEL",
    "SHERPA_ONNX_WHISPER_ENCODER",
    "SHERPA_ONNX_WHISPER_DECODER",
    "SHERPA_ONNX_WHISPER_LANGUAGE",
    "SHERPA_ONNX_WHISPER_TASK",
    "SHERPA_ONNX_WHISPER_TAIL_PADDINGS",
    "SHERPA_ONNX_NUM_THREADS",
    "SHERPA_ONNX_DECODING_METHOD",
    "SHERPA_ONNX_DEBUG",
    "SHERPA_ONNX_SAMPLE_RATE",
    "SHERPA_ONNX_FEATURE_DIM",
}

_ENV_TO_ATTR: dict[str, str] = {
    "VOICE_TRANSCRIBE_PROVIDER": "voice_transcribe_provider",
    "SHERPA_ASR_ENABLED": "sherpa_asr_enabled",
    "SHERPA_ASR_MODE": "sherpa_asr_mode",
    "SHERPA_ASR_REMOTE_URL": "sherpa_asr_remote_url",
    "SHERPA_ONNX_TOKENS": "sherpa_onnx_tokens",
    "SHERPA_ONNX_WENET_CTC_MODEL": "sherpa_onnx_wenet_ctc_model",
    "SHERPA_ONNX_WHISPER_ENCODER": "sherpa_onnx_whisper_encoder",
    "SHERPA_ONNX_WHISPER_DECODER": "sherpa_onnx_whisper_decoder",
    "SHERPA_ONNX_WHISPER_LANGUAGE": "sherpa_onnx_whisper_language",
    "SHERPA_ONNX_WHISPER_TASK": "sherpa_onnx_whisper_task",
    "SHERPA_ONNX_WHISPER_TAIL_PADDINGS": "sherpa_onnx_whisper_tail_paddings",
    "SHERPA_ONNX_NUM_THREADS": "sherpa_onnx_num_threads",
    "SHERPA_ONNX_DECODING_METHOD": "sherpa_onnx_decoding_method",
    "SHERPA_ONNX_DEBUG": "sherpa_onnx_debug",
    "SHERPA_ONNX_SAMPLE_RATE": "sherpa_onnx_sample_rate",
    "SHERPA_ONNX_FEATURE_DIM": "sherpa_onnx_feature_dim",
}


def _parse_bool(value: object | None, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return bool(int(value))
    s = str(value).strip().lower()
    if not s:
        return bool(default)
    return s in {"1", "true", "yes", "y", "on"}


def _parse_int(value: object | None, default: int) -> int:
    try:
        if value is None:
            return int(default)
        if isinstance(value, bool):
            return int(default)
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return int(value)
        s = str(value).strip()
        if not s:
            return int(default)
        return int(float(s))
    except Exception:
        return int(default)


class _SettingsOverlay:
    def __init__(self, base: Any, overrides: dict[str, Any]):
        self._base = base
        self._overrides = overrides

    def __getattr__(self, name: str) -> Any:
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._base, name)


async def load_voice_config_overrides(db: AsyncSession) -> dict[str, str]:
    from ..models.system import SystemConfig

    res = await db.execute(select(SystemConfig.key, SystemConfig.value).where(SystemConfig.key.in_(VOICE_CONFIG_KEYS)))
    rows = res.all()

    out: dict[str, str] = {}
    for key, value in rows:
        k = str(key or "").strip()
        if not k:
            continue
        v = "" if value is None else str(value)
        out[k] = v
    return out


async def get_effective_voice_settings(
    db: AsyncSession,
    base_settings: Any,
) -> tuple[Any, dict[str, str], bool]:
    overrides = await load_voice_config_overrides(db)

    force_raw = overrides.get("VOICE_TRANSCRIBE_FORCE_ENABLED")
    if force_raw is None or (not str(force_raw).strip()):
        force_raw = os.getenv("VOICE_TRANSCRIBE_FORCE_ENABLED", "")

    force_enabled = _parse_bool(force_raw, bool(getattr(base_settings, "voice_transcribe_force_enabled", False)))

    if not force_enabled:
        return base_settings, {}, False

    merged: dict[str, Any] = {}

    for env_key, attr in _ENV_TO_ATTR.items():
        raw = overrides.get(env_key)
        if raw is None:
            continue
        if not str(raw).strip():
            continue

        if attr in {"sherpa_asr_enabled", "sherpa_onnx_debug"}:
            merged[attr] = _parse_bool(raw, bool(getattr(base_settings, attr, False)))
            continue

        if attr in {
            "sherpa_onnx_whisper_tail_paddings",
            "sherpa_onnx_num_threads",
            "sherpa_onnx_sample_rate",
            "sherpa_onnx_feature_dim",
        }:
            merged[attr] = _parse_int(raw, int(getattr(base_settings, attr, 0) or 0))
            continue

        merged[attr] = str(raw)

    provider = str(merged.get("voice_transcribe_provider", getattr(base_settings, "voice_transcribe_provider", "auto")) or "").strip().lower()
    if provider not in {"auto", "openai", "sherpa"}:
        provider = "auto"
    merged["voice_transcribe_provider"] = provider

    mode = str(merged.get("sherpa_asr_mode", getattr(base_settings, "sherpa_asr_mode", "off")) or "").strip().lower()
    if mode not in {"off", "local", "remote"}:
        mode = "off"
    merged["sherpa_asr_mode"] = mode

    return _SettingsOverlay(base_settings, merged), overrides, True
