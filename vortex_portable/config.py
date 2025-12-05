"""Configuration helpers for the VortexAI portable assistant."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


@dataclass
class AppConfig:
    """
    Runtime configuration for the assistant.

    Attributes:
        base_url: Root URL for the Vortex `/chat` endpoint (without trailing slash).
        api_key: Optional bearer token sent as `Authorization: Bearer <token>`.
        request_timeout: HTTP timeout in seconds.
        system_prompt: Optional system message seeded into the chat history.
        wake_word: Keyword the wake detector waits for in the CLI harness.
        language: Optional BCP-47 code passed to STT implementations.
        conversation_id: Conversation identifier reused per session for backend context.
        debug: Whether to set debug=true on chat requests.
        mode: "console" or "audio" for selecting implementations.
        stt_mode: "local", "remote", or "wyoming" for STT implementation.
        tts_mode: "local", "remote", or "wyoming" for TTS implementation.
        whisper_url: URL for remote Whisper service (when stt_mode=remote).
        piper_url: URL for remote Piper service (when tts_mode=remote).
        whisper_host: Wyoming Whisper host (when stt_mode=wyoming).
        whisper_port: Wyoming Whisper port (when stt_mode=wyoming).
        piper_host: Wyoming Piper host (when tts_mode=wyoming).
        piper_port: Wyoming Piper port (when tts_mode=wyoming).
        whisper_model: Whisper model size for STT (audio mode, local).
        whisper_device: Device for Whisper ("cpu"/"cuda"/None).
        record_seconds: Duration to record per utterance in audio mode.
        piper_model_path: Path to a Piper `.onnx` model (audio mode, local).
        piper_binary: Piper binary name/path (audio mode, local).
        piper_speaker: Optional speaker id/name for Piper.
        wake_model_path: Optional openWakeWord model path; defaults to built-ins.

    Usage:
        >>> config = AppConfig.from_env()
        >>> config.base_url
        'http://localhost:8000'
    """

    base_url: str
    api_key: Optional[str]
    request_timeout: float
    system_prompt: Optional[str]
    wake_word: str
    language: Optional[str]
    conversation_id: str
    debug: bool
    mode: str
    stt_mode: str
    tts_mode: str
    whisper_url: Optional[str]
    piper_url: Optional[str]
    whisper_host: str
    whisper_port: int
    piper_host: str
    piper_port: int
    whisper_model: str
    whisper_device: Optional[str]
    record_seconds: float
    piper_model_path: Optional[str]
    piper_binary: str
    piper_speaker: Optional[str]
    wake_model_path: Optional[str]

    @classmethod
    def from_env(cls) -> "AppConfig":
        """
        Build an :class:`AppConfig` from environment variables.

        Supported variables:
            - VORTEX_API_BASE_URL: Root URL for the Vortex service (default: http://localhost:8000)
            - VORTEX_API_KEY: Optional bearer token for authorization.
            - VORTEX_REQUEST_TIMEOUT: Timeout in seconds (float, default: 10).
            - VORTEX_SYSTEM_PROMPT: Seed system message (default: polite helper prompt).
            - VORTEX_WAKE_WORD: Wake keyword (default: "hey vortex").
            - VORTEX_LANGUAGE: Language hint for STT (e.g., "en-US").
            - VORTEX_CONVERSATION_ID: Explicit conversation id; defaults to a random UUID.
            - VORTEX_DEBUG: "true"/"1" to enable debug flag on chat requests (default: false).
            - VORTEX_MODE: "console" (default) or "audio" to enable mic + TTS.
            - VORTEX_STT_MODE: "local" (default), "remote", or "wyoming" for STT.
            - VORTEX_TTS_MODE: "local" (default), "remote", or "wyoming" for TTS.
            - VORTEX_WHISPER_URL: URL for remote Whisper (HTTP) service.
            - VORTEX_PIPER_URL: URL for remote Piper (HTTP) service.
            - VORTEX_WHISPER_HOST: Wyoming Whisper host (default: "localhost").
            - VORTEX_WHISPER_PORT: Wyoming Whisper port (default: 10300).
            - VORTEX_PIPER_HOST: Wyoming Piper host (default: "localhost").
            - VORTEX_PIPER_PORT: Wyoming Piper port (default: 10200).
            - VORTEX_WHISPER_MODEL: Whisper model size (default: "tiny").
            - VORTEX_WHISPER_DEVICE: Whisper device (e.g., "cuda" or "cpu").
            - VORTEX_RECORD_SECONDS: Seconds per utterance recording in audio mode (default: 5).
            - VORTEX_PIPER_MODEL: Path to Piper .onnx model (required for audio mode).
            - VORTEX_PIPER_BINARY: Piper binary name/path (default: "piper").
            - VORTEX_PIPER_SPEAKER: Optional speaker id/name passed to Piper.
            - VORTEX_WAKE_MODEL: Optional openWakeWord model path; defaults to built-ins.
        """

        base_url = os.environ.get("VORTEX_API_BASE_URL", "http://localhost:8000").rstrip("/")
        api_key = os.environ.get("VORTEX_API_KEY") or None
        timeout_raw = os.environ.get("VORTEX_REQUEST_TIMEOUT", "10")
        try:
            request_timeout = float(timeout_raw)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("VORTEX_REQUEST_TIMEOUT must be a number") from exc

        system_prompt = os.environ.get(
            "VORTEX_SYSTEM_PROMPT",
            "You are Vortex, a concise and helpful on-device assistant.",
        )
        wake_word = os.environ.get("VORTEX_WAKE_WORD", "hey vortex").strip()
        language = os.environ.get("VORTEX_LANGUAGE") or None
        conversation_id = os.environ.get("VORTEX_CONVERSATION_ID") or ""
        debug_raw = os.environ.get("VORTEX_DEBUG", "false").lower()
        debug = debug_raw in {"1", "true", "yes", "on"}
        mode = os.environ.get("VORTEX_MODE", "console").lower()
        stt_mode = os.environ.get("VORTEX_STT_MODE", "local").lower()
        tts_mode = os.environ.get("VORTEX_TTS_MODE", "local").lower()
        whisper_url = os.environ.get("VORTEX_WHISPER_URL") or None
        piper_url = os.environ.get("VORTEX_PIPER_URL") or None
        whisper_host = os.environ.get("VORTEX_WHISPER_HOST", "localhost")
        whisper_port_raw = os.environ.get("VORTEX_WHISPER_PORT", "10300")
        try:
            whisper_port = int(whisper_port_raw)
        except ValueError as exc:
            raise ValueError("VORTEX_WHISPER_PORT must be an integer") from exc
        piper_host = os.environ.get("VORTEX_PIPER_HOST", "localhost")
        piper_port_raw = os.environ.get("VORTEX_PIPER_PORT", "10200")
        try:
            piper_port = int(piper_port_raw)
        except ValueError as exc:
            raise ValueError("VORTEX_PIPER_PORT must be an integer") from exc
        whisper_model = os.environ.get("VORTEX_WHISPER_MODEL", "tiny")
        whisper_device = os.environ.get("VORTEX_WHISPER_DEVICE") or None
        record_seconds_raw = os.environ.get("VORTEX_RECORD_SECONDS", "5")
        try:
            record_seconds = float(record_seconds_raw)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("VORTEX_RECORD_SECONDS must be a number") from exc
        piper_model_path = os.environ.get("VORTEX_PIPER_MODEL") or None
        piper_binary = os.environ.get("VORTEX_PIPER_BINARY", "piper")
        piper_speaker = os.environ.get("VORTEX_PIPER_SPEAKER") or None
        wake_model_path = os.environ.get("VORTEX_WAKE_MODEL") or None

        return cls(
            base_url=base_url,
            api_key=api_key,
            request_timeout=request_timeout,
            system_prompt=system_prompt,
            wake_word=wake_word or "hey vortex",
            language=language,
            conversation_id=conversation_id,
            debug=debug,
            mode=mode,
            stt_mode=stt_mode,
            tts_mode=tts_mode,
            whisper_url=whisper_url,
            piper_url=piper_url,
            whisper_host=whisper_host,
            whisper_port=whisper_port,
            piper_host=piper_host,
            piper_port=piper_port,
            whisper_model=whisper_model,
            whisper_device=whisper_device,
            record_seconds=record_seconds,
            piper_model_path=piper_model_path,
            piper_binary=piper_binary,
            piper_speaker=piper_speaker,
            wake_model_path=wake_model_path,
        )
