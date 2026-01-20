import asyncio
import io
import os
import subprocess
import tempfile
import threading
from typing import Any, Literal

import httpx
try:
    import numpy as np
except Exception:
    np = None

try:
    import sherpa_onnx  # type: ignore
except Exception:
    sherpa_onnx = None


SherpaMode = Literal["off", "local", "remote"]


def _get_setting(settings: Any, key: str, default: Any) -> Any:
    try:
        return getattr(settings, key)
    except Exception:
        return default


def _normalize_mode(value: Any) -> SherpaMode:
    s = str(value or "").strip().lower()
    if s in {"local", "remote"}:
        return s  # type: ignore
    return "off"


def sherpa_is_ready(settings: Any) -> bool:
    enabled = bool(_get_setting(settings, "sherpa_asr_enabled", False))
    if not enabled:
        return False

    mode = _normalize_mode(_get_setting(settings, "sherpa_asr_mode", "off"))
    if mode == "off":
        return False

    if mode == "remote":
        url = str(_get_setting(settings, "sherpa_asr_remote_url", "") or "").strip()
        return bool(url)

    if np is None:
        return False

    if sherpa_onnx is None:
        return False

    tokens = str(_get_setting(settings, "sherpa_onnx_tokens", "") or "").strip()
    wenet_ctc = str(_get_setting(settings, "sherpa_onnx_wenet_ctc_model", "") or "").strip()
    whisper_encoder = str(_get_setting(settings, "sherpa_onnx_whisper_encoder", "") or "").strip()
    whisper_decoder = str(_get_setting(settings, "sherpa_onnx_whisper_decoder", "") or "").strip()

    if tokens and wenet_ctc:
        return os.path.exists(tokens) and os.path.exists(wenet_ctc)

    if tokens and whisper_encoder and whisper_decoder:
        return os.path.exists(tokens) and os.path.exists(whisper_encoder) and os.path.exists(whisper_decoder)

    return False


def _ffmpeg_available() -> bool:
    try:
        cp = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=3,
        )
        return cp.returncode == 0
    except Exception:
        return False


def _read_wav_bytes(data: bytes) -> tuple[Any, int]:
    if np is None:
        raise RuntimeError("numpy_not_installed")
    assert np is not None
    with wave_open(io.BytesIO(data)) as wf:
        sr = int(wf.getframerate())
        n_channels = int(wf.getnchannels())
        sampwidth = int(wf.getsampwidth())
        n_frames = int(wf.getnframes())
        raw = wf.readframes(n_frames)

    if sampwidth != 2:
        raise ValueError("unsupported_wav_sample_width")

    pcm = np.frombuffer(raw, dtype=np.int16)
    if n_channels > 1:
        pcm = pcm.reshape(-1, n_channels)[:, 0]

    samples = (pcm.astype(np.float32) / 32768.0).copy()
    return samples, sr


def wave_open(file_obj: io.BytesIO):
    import wave

    return wave.open(file_obj, "rb")


def _convert_with_ffmpeg_to_wav_16k_mono(content: bytes, suffix: str) -> bytes:
    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg_not_available")

    in_path = None
    out_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            in_path = f.name
            f.write(content)

        out_fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(out_fd)

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            in_path,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            out_path,
        ]
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30)
        if cp.returncode != 0:
            raise RuntimeError("ffmpeg_convert_failed")

        with open(out_path, "rb") as f:
            return f.read()
    finally:
        for p in (in_path, out_path):
            if p:
                try:
                    os.remove(p)
                except Exception:
                    pass


def _audio_to_float32_16k(content: bytes, filename: str) -> tuple[Any, int]:
    suffix = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""

    try:
        samples, sr = _read_wav_bytes(content)
        if sr != 16000:
            wav = _convert_with_ffmpeg_to_wav_16k_mono(content, suffix=suffix or ".wav")
            return _read_wav_bytes(wav)
        return samples, sr
    except Exception:
        wav = _convert_with_ffmpeg_to_wav_16k_mono(content, suffix=suffix or ".bin")
        return _read_wav_bytes(wav)


class _SherpaLocalSingleton:
    _lock = threading.Lock()
    _recognizer: Any = None
    _fingerprint: tuple[str, ...] | None = None

    @classmethod
    def _build_recognizer(cls, settings: Any):
        if np is None:
            raise RuntimeError("numpy_not_installed")
        if sherpa_onnx is None:
            raise RuntimeError("sherpa_onnx_not_installed")
        assert sherpa_onnx is not None

        tokens = str(_get_setting(settings, "sherpa_onnx_tokens", "") or "").strip()
        wenet_ctc = str(_get_setting(settings, "sherpa_onnx_wenet_ctc_model", "") or "").strip()
        whisper_encoder = str(_get_setting(settings, "sherpa_onnx_whisper_encoder", "") or "").strip()
        whisper_decoder = str(_get_setting(settings, "sherpa_onnx_whisper_decoder", "") or "").strip()

        num_threads = int(_get_setting(settings, "sherpa_onnx_num_threads", 2) or 2)
        decoding_method = str(_get_setting(settings, "sherpa_onnx_decoding_method", "greedy_search") or "greedy_search")
        debug = bool(_get_setting(settings, "sherpa_onnx_debug", False))

        sample_rate = int(_get_setting(settings, "sherpa_onnx_sample_rate", 16000) or 16000)
        feature_dim = int(_get_setting(settings, "sherpa_onnx_feature_dim", 80) or 80)

        if tokens and wenet_ctc:
            cls._fingerprint = ("wenet_ctc", tokens, wenet_ctc, str(num_threads), decoding_method, str(sample_rate), str(feature_dim))
            return sherpa_onnx.OfflineRecognizer.from_wenet_ctc(
                model=wenet_ctc,
                tokens=tokens,
                num_threads=num_threads,
                sample_rate=sample_rate,
                feature_dim=feature_dim,
                decoding_method=decoding_method,
                debug=debug,
            )

        if tokens and whisper_encoder and whisper_decoder:
            language = str(_get_setting(settings, "sherpa_onnx_whisper_language", "") or "")
            task = str(_get_setting(settings, "sherpa_onnx_whisper_task", "transcribe") or "transcribe")
            tail_paddings = int(_get_setting(settings, "sherpa_onnx_whisper_tail_paddings", -1) or -1)
            cls._fingerprint = (
                "whisper",
                tokens,
                whisper_encoder,
                whisper_decoder,
                str(num_threads),
                decoding_method,
                language,
                task,
                str(tail_paddings),
            )
            return sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=whisper_encoder,
                decoder=whisper_decoder,
                tokens=tokens,
                num_threads=num_threads,
                decoding_method=decoding_method,
                debug=debug,
                language=language,
                task=task,
                tail_paddings=tail_paddings,
            )

        raise RuntimeError("sherpa_model_not_configured")

    @classmethod
    def get_recognizer(cls, settings: Any):
        with cls._lock:
            desired_tokens = str(_get_setting(settings, "sherpa_onnx_tokens", "") or "").strip()
            desired_wenet = str(_get_setting(settings, "sherpa_onnx_wenet_ctc_model", "") or "").strip()
            desired_we = str(_get_setting(settings, "sherpa_onnx_whisper_encoder", "") or "").strip()
            desired_wd = str(_get_setting(settings, "sherpa_onnx_whisper_decoder", "") or "").strip()

            desired_fp = None
            if desired_tokens and desired_wenet:
                desired_fp = ("wenet_ctc", desired_tokens, desired_wenet)
            elif desired_tokens and desired_we and desired_wd:
                desired_fp = ("whisper", desired_tokens, desired_we, desired_wd)

            if cls._recognizer is not None and cls._fingerprint is not None and desired_fp is not None:
                if tuple(cls._fingerprint[: len(desired_fp)]) == tuple(desired_fp):
                    return cls._recognizer

            cls._recognizer = cls._build_recognizer(settings)
            return cls._recognizer


def _transcribe_local_sync(content: bytes, filename: str, settings: Any) -> str:
    if np is None:
        raise RuntimeError("numpy_not_installed")
    samples, sr = _audio_to_float32_16k(content, filename)
    rec = _SherpaLocalSingleton.get_recognizer(settings)
    s = rec.create_stream()
    s.accept_waveform(sr, samples)
    rec.decode_streams([s])
    return str(getattr(getattr(s, "result", None), "text", "") or "")


async def sherpa_transcribe(
    *,
    content: bytes,
    filename: str,
    settings: Any,
    segment_index: int | None = None,
    is_final: bool | None = None,
) -> tuple[str, str, str | None]:
    enabled = bool(_get_setting(settings, "sherpa_asr_enabled", False))
    mode = _normalize_mode(_get_setting(settings, "sherpa_asr_mode", "off"))

    if not enabled or mode == "off":
        raise RuntimeError("sherpa_disabled")

    if mode == "remote":
        url = str(_get_setting(settings, "sherpa_asr_remote_url", "") or "").strip()
        if not url:
            raise RuntimeError("sherpa_remote_url_missing")

        data: dict[str, str] = {}
        if segment_index is not None:
            data["segment_index"] = str(int(segment_index))
        if is_final is not None:
            data["is_final"] = "true" if bool(is_final) else "false"

        files = {"file": (filename, content, "application/octet-stream")}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, data=data, files=files)
            resp.raise_for_status()
            payload = resp.json()
            text = str(payload.get("text", "") if isinstance(payload, dict) else "")
        return text, "sherpa_remote", url

    text = await asyncio.to_thread(_transcribe_local_sync, content, filename, settings)
    return text, "sherpa_local", None
