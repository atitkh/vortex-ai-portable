"""CLI harness for the VortexAI portable assistant."""

from __future__ import annotations

import argparse
import logging
from typing import Optional

from .config import AppConfig
from .pipeline import PortableAssistant
from .services.chat_client import HttpChatClient
from .services.mic_recorder import SoundDeviceRecorder
from .services.recorder import ConsoleRecorder
from .services.stt import EchoSpeechToText
from .services.stt_whisper import WhisperSpeechToText
from .services.stt_remote import RemoteSpeechToText
from .services.stt_wyoming import WyomingSpeechToText
from .services.tts_piper import PiperTextToSpeech
from .services.tts_remote import RemoteTextToSpeech
from .services.tts_wyoming import WyomingTextToSpeech
from .services.tts import ConsoleTextToSpeech
from .services.wake_word import KeywordWakeWordDetector
from .services.wake_openwakeword import OpenWakeWordDetector


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def build_assistant(config: AppConfig) -> PortableAssistant:
    """Wire up the assistant with default console or audio implementations."""
    chat_client = HttpChatClient(config.base_url, api_key=config.api_key, timeout=config.request_timeout)

    if config.mode == "audio":
        wake = OpenWakeWordDetector(model_path=config.wake_model_path)
        # VAD-based recorder (stops automatically when you stop speaking)
        recorder = SoundDeviceRecorder(
            sample_rate=16000,
            max_seconds=config.record_seconds,
            silence_duration=config.silence_duration,
            silence_threshold=0.01,
        )
        
        # Choose STT implementation based on config
        if config.stt_mode == "remote":
            if not config.whisper_url:
                raise RuntimeError("VORTEX_WHISPER_URL must be set when VORTEX_STT_MODE=remote.")
            stt = RemoteSpeechToText(base_url=config.whisper_url)
        elif config.stt_mode == "wyoming":
            stt = WyomingSpeechToText(
                host=config.whisper_host,
                port=config.whisper_port,
            )
        else:
            stt = WhisperSpeechToText(model_size=config.whisper_model, device=config.whisper_device)
        
        # Choose TTS implementation based on config
        if config.tts_mode == "remote":
            if not config.piper_url:
                raise RuntimeError("VORTEX_PIPER_URL must be set when VORTEX_TTS_MODE=remote.")
            tts = RemoteTextToSpeech(base_url=config.piper_url, speaker=config.piper_speaker)
        elif config.tts_mode == "wyoming":
            tts = WyomingTextToSpeech(
                host=config.piper_host,
                port=config.piper_port,
                speaker=config.piper_speaker,
            )
        else:
            if not config.piper_model_path:
                raise RuntimeError("VORTEX_PIPER_MODEL must be set when VORTEX_TTS_MODE=local.")
            tts = PiperTextToSpeech(
                model_path=config.piper_model_path,
                binary_path=config.piper_binary,
                speaker=config.piper_speaker,
            )
    else:
        wake = KeywordWakeWordDetector(config.wake_word)
        recorder = ConsoleRecorder()
        stt = EchoSpeechToText()
        tts = ConsoleTextToSpeech()

    return PortableAssistant(
        wake_detector=wake,
        recorder=recorder,
        stt=stt,
        chat_client=chat_client,
        tts=tts,
        system_prompt=config.system_prompt,
        language=config.language,
        conversation_id=config.conversation_id or None,
        debug=config.debug,
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the VortexAI portable assistant (CLI harness).")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--mode",
        choices=["console", "audio"],
        help="Override VORTEX_MODE (console/audio).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    _configure_logging(args.verbose)
    config = AppConfig.from_env()
    if args.mode:
        config.mode = args.mode
    assistant = build_assistant(config)
    assistant.run_forever()


if __name__ == "__main__":
    main()
