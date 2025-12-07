"""Microphone recorder backed by sounddevice with Voice Activity Detection."""

from __future__ import annotations

import time
from typing import Optional

from ..interfaces import AudioRecorder
from ..models import CapturedAudio


class SoundDeviceRecorder(AudioRecorder):
    """
    Records audio from the default microphone using sounddevice with VAD.

    Args:
        sample_rate: Target sample rate (Hz).
        channels: Number of channels to record.
        max_seconds: Maximum recording duration (safety limit).
        silence_duration: Seconds of silence before stopping (VAD).
        silence_threshold: Audio level below which is considered silence.

    Usage:
        recorder = SoundDeviceRecorder(sample_rate=16000, max_seconds=30)
        audio = recorder.record()
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        channels: int = 1,
        max_seconds: float = 30.0,
        silence_duration: float = 1.5,
        silence_threshold: float = 0.01,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds
        self.silence_duration = silence_duration
        self.silence_threshold = silence_threshold

    def record(self) -> CapturedAudio:
        sd = _lazy_import_sounddevice()
        import numpy as np

        if self.max_seconds > 0:
            print(f"[rec] Listening... speak now (max {self.max_seconds}s, stops after {self.silence_duration}s of silence)")
        else:
            print(f"[rec] Listening... speak now (stops after {self.silence_duration}s of silence)")
        
        recorded_chunks = []
        silence_start = None
        recording_started = False
        start_time = time.time()
        
        def callback(indata, frames, time_info, status):
            nonlocal silence_start, recording_started
            if status:
                print(f"[rec] Status: {status}")
            
            # Calculate audio level
            audio_level = np.abs(indata).mean()
            
            # Detect if speech is present
            if audio_level > self.silence_threshold:
                recording_started = True
                silence_start = None
                recorded_chunks.append(indata.copy())
            elif recording_started:
                # Speech has started, now detecting silence
                recorded_chunks.append(indata.copy())
                if silence_start is None:
                    silence_start = time.time()
        
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                callback=callback,
            ):
                while True:
                    sd.sleep(100)  # Check every 100ms
                    
                    # Stop if max duration reached (if max_seconds > 0)
                    if self.max_seconds > 0 and time.time() - start_time > self.max_seconds:
                        print(f"[rec] Max duration reached ({self.max_seconds}s)")
                        break
                    
                    # Stop if silence detected after speech
                    if recording_started and silence_start is not None:
                        if time.time() - silence_start > self.silence_duration:
                            print(f"[rec] Silence detected, stopping")
                            break
        
        except KeyboardInterrupt:
            print("\n[rec] Recording interrupted")
        
        if not recorded_chunks:
            print("[rec] No audio recorded")
            return CapturedAudio(
                data=b"",
                sample_rate=self.sample_rate,
                transcript_hint=None,
                encoding="pcm_s16le",
            )
        
        # Combine all chunks
        recording = np.concatenate(recorded_chunks, axis=0)
        duration = len(recording) / self.sample_rate
        print(f"[rec] Recorded {duration:.2f}s of audio")
        
        # Play end of listening sound
        print("[rec] Playing end sound...")
        try:
            from .audio_feedback import play_double_beep
            play_double_beep()
            print("[rec] End sound played")
        except Exception as e:
            print(f"[rec] Failed to play end sound: {e}")

        # Convert float32 [-1.0, 1.0] to 16-bit PCM bytes
        pcm = np.clip(recording, -1.0, 1.0)
        pcm_int16 = (pcm * 32767).astype("int16")
        data = pcm_int16.tobytes()

        return CapturedAudio(
            data=data,
            sample_rate=self.sample_rate,
            transcript_hint=None,
            encoding="pcm_s16le",
        )


def _lazy_import_sounddevice():
    try:
        import sounddevice as sd  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("sounddevice is required for microphone recording. Install via pip.") from exc
    return sd
