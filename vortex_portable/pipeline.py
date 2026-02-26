"""Core orchestration for the portable assistant."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Optional

from .exceptions import ChatClientError
from .interfaces import AudioRecorder, ChatClient, SpeechToText, StreamingChatClient, TextToSpeech, WakeWordDetector
from .utils import SentenceSplitter

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
        enable_audio_feedback: bool = True,
        follow_up_timeout: float = 12.0,
        allow_interruption: bool = True,
    ) -> None:
        self._wake_detector = wake_detector
        self._recorder = recorder
        self._stt = stt
        self._chat_client = chat_client
        self._tts = tts
        self._language = language
        self._conversation_id = conversation_id or f"session-{uuid.uuid4()}"
        self._debug = debug
        self._enable_audio_feedback = enable_audio_feedback
        self._system_prompt = system_prompt
        self._follow_up_timeout = follow_up_timeout
        self._allow_interruption = allow_interruption
        self._interrupted = threading.Event()  # Set when user interrupts TTS

        # Check if chat client supports streaming
        self._supports_streaming = isinstance(chat_client, StreamingChatClient)
        if self._supports_streaming:
            logger.info("Chat client supports streaming - enabling sentence-based TTS")

    def run_forever(self) -> None:
        """Main loop: wait for wake word, then hold conversation until silence."""
        logger.info("Assistant ready. Waiting for wake word.")
        while True:
            woken = self._wake_detector.await_wake_word()
            if not woken:
                logger.info("Wake detector requested shutdown.")
                return
            self._run_conversation_session()

    def _run_conversation_session(self) -> None:
        """
        Run a full conversation session after wake word.
        Keeps listening for follow-ups without requiring wake word again.
        Exits when user stops responding within follow_up_timeout.
        """
        while True:
            try:
                interrupted = self._process_one_interaction()
            except ChatClientError as exc:
                logger.error("Chat error: %s", exc)
                print(f"[error] {exc}")
                return
            except Exception as exc:
                logger.exception("Unexpected error: %s", exc)
                return

            if interrupted:
                # User barged in — immediately loop for next turn
                print("[pipeline] Interrupted — listening for follow-up...")
                continue

            # Wait for follow-up speech within timeout window
            print(f"[pipeline] Listening for follow-up ({self._follow_up_timeout:.0f}s)...")
            if not self._wait_for_speech(timeout=self._follow_up_timeout):
                print("[pipeline] No follow-up detected, returning to wake word.")
                return
            # Speech detected in follow-up window — loop without wake word

    def _wait_for_speech(self, timeout: float) -> bool:
        """
        Monitor microphone for speech within a timeout window.
        Returns True if speech detected, False if timeout.
        """
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            # No sounddevice — can't monitor, just wait
            time.sleep(timeout)
            return False

        speech_detected = threading.Event()
        deadline = time.time() + timeout

        def callback(indata, frames, time_info, status):
            if speech_detected.is_set():
                return
            level = float(np.abs(indata).mean())
            if level > 0.02:  # Simple amplitude gate for follow-up detection
                speech_detected.set()

        try:
            with sd.InputStream(
                channels=1,
                dtype="float32",
                blocksize=512,
                device=sd.default.device[0],
                callback=callback,
            ):
                while not speech_detected.is_set():
                    if time.time() >= deadline:
                        return False
                    time.sleep(0.05)
            return True
        except Exception as e:
            logger.debug(f"Follow-up monitor error: {e}")
            return False

    def _start_interruption_monitor(self, stop_event: threading.Event) -> threading.Thread:
        """
        Start a background thread that monitors mic and calls sd.stop()
        if the user starts speaking while TTS is playing.
        """
        def monitor():
            try:
                import sounddevice as sd
                import numpy as np
            except ImportError:
                return

            def callback(indata, frames, time_info, status):
                if stop_event.is_set():
                    return
                level = float(np.abs(indata).mean())
                if level > 0.02:
                    print("\n[pipeline] Interrupted by user speech")
                    stop_event.set()
                    self._interrupted.set()

            try:
                with sd.InputStream(
                    channels=1,
                    dtype="float32",
                    blocksize=512,
                    device=sd.default.device[0],
                    callback=callback,
                ):
                    while not stop_event.is_set():
                        time.sleep(0.05)
                # Stop TTS playback after exiting stream context
                if self._interrupted.is_set():
                    sd.stop()
            except Exception as e:
                logger.debug(f"Interruption monitor error: {e}")

        t = threading.Thread(target=monitor, daemon=True)
        t.start()
        return t

    def _process_one_interaction(self) -> bool:
        """Run one listen→transcribe→chat→speak cycle. Returns True if interrupted."""
        self._interrupted.clear()
        if self._enable_audio_feedback:
            self._play_audio_feedback("listening")
        
        print("\n[pipeline] → Recording audio...")
        audio = self._recorder.record()
        
        # Audio feedback: processing
        if self._enable_audio_feedback:
            self._play_audio_feedback("processing")
        
        print(f"[pipeline] → Transcribing {len(audio.data)} bytes...")
        user_text = self._stt.transcribe(audio, language=self._language).strip()
        if not user_text:
            print("[pipeline] ✗ No speech captured. Try again.")
            if self._enable_audio_feedback:
                self._play_audio_feedback("error")
            return False

        print(f"[pipeline] ✓ You said: {user_text}")
        
        # Audio feedback: thinking
        if self._enable_audio_feedback:
            self._play_audio_feedback("thinking")
        
        print(f"[pipeline] → Sending to chat service...")
        
        # Use streaming if supported
        if self._supports_streaming:
            self._process_streaming_response(user_text)
        else:
            self._process_non_streaming_response(user_text)
        
        print(f"[pipeline] ✓ Done\n")
        return self._interrupted.is_set()
    
    def _process_streaming_response(self, user_text: str) -> None:
        """Process streaming response with sentence-based TTS."""
        stop_event = threading.Event()
        if self._allow_interruption:
            self._start_interruption_monitor(stop_event)

        try:
            if self._enable_audio_feedback:
                self._play_audio_feedback("speaking")
            
            print(f"[pipeline] → Streaming response...")
            splitter = SentenceSplitter()
            
            for chunk in self._chat_client.chat_stream(  # type: ignore[attr-defined]
                user_text,
                conversation_id=self._conversation_id,
                debug=self._debug,
            ):
                if self._interrupted.is_set():
                    break

                for sentence in splitter.add(chunk):
                    if self._interrupted.is_set():
                        break
                    print(f"[pipeline] 🗣  {sentence}")
                    self._tts.speak(sentence)
            
            if not self._interrupted.is_set():
                remaining = splitter.flush()
                if remaining:
                    print(f"[pipeline] 🗣  {remaining}")
                    self._tts.speak(remaining)
            
        except ChatClientError as exc:
            print(f"[error] {exc}")
            if self._enable_audio_feedback:
                self._play_audio_feedback("error")
            raise
        finally:
            stop_event.set()  # Always stop interruption monitor
    
    def _process_non_streaming_response(self, user_text: str) -> None:
        """Process non-streaming response."""
        response = self._chat_client.chat(
            user_text,
            conversation_id=self._conversation_id,
            debug=self._debug,
        )

        print(f"[pipeline] ✓ Got response: {response.text[:100]}{'...' if len(response.text) > 100 else ''}")

        stop_event = threading.Event()
        if self._allow_interruption:
            self._start_interruption_monitor(stop_event)

        try:
            if self._enable_audio_feedback:
                self._play_audio_feedback("speaking")
            print(f"[pipeline] → Speaking response...")
            self._tts.speak(response.text)
        finally:
            stop_event.set()
    
    def _play_audio_feedback(self, event: str) -> None:
        """Play audio feedback for different events."""
        try:
            from .services.audio_feedback import (
                play_wake_sound,
                play_double_beep,
                play_thinking_sound,
                play_speaking_start_sound,
                play_error_sound,
            )
            
            if event == "listening":
                play_wake_sound()
            elif event == "processing":
                play_double_beep()
            elif event == "thinking":
                play_thinking_sound()
            elif event == "speaking":
                play_speaking_start_sound()
            elif event == "error":
                play_error_sound()
        except Exception as e:
            # Don't let audio feedback errors break the pipeline
            logger.debug(f"Audio feedback error: {e}")

    @property
    def session_id(self) -> str:
        """The session ID used for OpenClaw conversation continuity."""
        return self._conversation_id
