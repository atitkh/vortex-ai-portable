"""Core orchestration for the portable assistant."""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional, Sequence

from .exceptions import ChatClientError
from .interfaces import AudioRecorder, ChatClient, SpeechToText, TextToSpeech, WakeWordDetector
from .models import Message

logger = logging.getLogger(__name__)


class PortableAssistant:
    """
    Runs the end-to-end assistant loop.

    Compose this class with concrete implementations of wake detection, recording,
    STT, chat service, and TTS. The defaults are provided by the CLI harness.

    Usage:
        assistant = PortableAssistant(
            wake_detector=KeywordWakeWordDetector("hey vortex"),
            recorder=ConsoleRecorder(),
            stt=EchoSpeechToText(),
            chat_client=HttpChatClient("http://localhost:8000"),
            tts=ConsoleTextToSpeech(),
            system_prompt="You are Vortex, a helpful assistant.",
        )
        assistant.run_forever()
    """

    def __init__(
        self,
        *,
        wake_detector: WakeWordDetector,
        recorder: AudioRecorder,
        stt: SpeechToText,
        chat_client: ChatClient,
        tts: TextToSpeech,
        system_prompt: Optional[str] = None,
        language: Optional[str] = None,
        conversation_id: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        self._wake_detector = wake_detector
        self._recorder = recorder
        self._stt = stt
        self._chat_client = chat_client
        self._tts = tts
        self._language = language
        self._conversation_id = conversation_id or f"session-{uuid.uuid4()}"
        self._debug = debug
        self._history: List[Message] = []

        if system_prompt:
            self._history.append(Message(role="system", content=system_prompt))

    def run_forever(self) -> None:
        """Main loop: wait for wake, record, transcribe, send, and speak."""
        logger.info("Assistant ready. Waiting for wake word.")
        while True:
            woken = self._wake_detector.await_wake_word()
            if not woken:
                logger.info("Wake detector requested shutdown.")
                return

            try:
                self._process_one_interaction()
            except ChatClientError as exc:
                logger.error("Chat error: %s", exc)
                print(f"[error] {exc}")
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Unexpected error during interaction: %s", exc)
                print(f"[unexpected error] {exc}")
            
            # Give a brief pause before listening for wake word again
            import time
            time.sleep(0.5)

    def _process_one_interaction(self) -> None:
        print("\n[pipeline] → Recording audio...")
        audio = self._recorder.record()
        
        print(f"[pipeline] → Transcribing {len(audio.data)} bytes...")
        user_text = self._stt.transcribe(audio, language=self._language).strip()
        if not user_text:
            print("[pipeline] ✗ No speech captured. Try again.")
            return

        print(f"[pipeline] ✓ You said: {user_text}")
        self._history.append(Message(role="user", content=user_text))
        
        print(f"[pipeline] → Sending to chat service...")
        response = self._chat_client.chat(
            user_text,
            conversation_id=self._conversation_id,
            debug=self._debug,
        )

        print(f"[pipeline] ✓ Got response: {response.text[:100]}{'...' if len(response.text) > 100 else ''}")
        assistant_message = Message(role="assistant", content=response.text)
        self._history.append(assistant_message)
        if response.conversation_id:
            self._conversation_id = response.conversation_id
        
        print(f"[pipeline] → Speaking response...")
        self._tts.speak(response.text)
        print(f"[pipeline] ✓ Done\n")

    @property
    def history(self) -> Sequence[Message]:
        """Read-only chat history accumulated during the session."""
        return tuple(self._history)
