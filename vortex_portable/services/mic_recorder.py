"""Microphone recorder backed by sounddevice with Silero VAD."""

from __future__ import annotations

import time
from typing import Optional

from ..interfaces import AudioRecorder
from ..models import CapturedAudio

# Silero VAD chunk size: 512 samples at 16kHz, 256 at 8kHz
_SILERO_CHUNK_SIZE = 512


def _load_silero_vad():
    """Load Silero VAD model. Returns model or None if unavailable."""
    try:
        from silero_vad import load_silero_vad  # pip install silero-vad
        model = load_silero_vad()
        return model
    except ImportError:
        pass
    except Exception as e:
        print(f"[vad] Silero VAD (pip) failed: {e}")
    
    # Fallback: try torch.hub (requires torchaudio)
    try:
        import torch
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
            verbose=False,
        )
        model.eval()
        return model
    except Exception as e:
        print(f"[vad] Silero VAD unavailable, falling back to amplitude threshold: {e}")
        return None


class SoundDeviceRecorder(AudioRecorder):
    """
    Records audio from the default microphone using sounddevice.

    Uses Silero VAD (ML-based) for accurate speech/silence detection.
    Falls back to amplitude threshold if torch/silero is not available.

    Args:
        sample_rate: Target sample rate (Hz). Must be 16000 for Silero VAD.
        channels: Number of channels to record.
        max_seconds: Maximum recording duration (safety limit).
        silence_duration: Seconds of silence before stopping.
        vad_threshold: Silero VAD speech probability threshold (0.0-1.0).
        amplitude_threshold: Fallback amplitude threshold if Silero unavailable.

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
        silence_duration: float = 1.2,
        vad_threshold: float = 0.5,
        amplitude_threshold: float = 0.01,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds
        self.silence_duration = silence_duration
        self.vad_threshold = vad_threshold
        self.amplitude_threshold = amplitude_threshold

        # Load Silero VAD model eagerly so first recording isn't delayed
        self._vad_model = _load_silero_vad()
        if self._vad_model:
            print("[vad] Silero VAD loaded")

    def _is_speech(self, chunk) -> bool:
        """Run chunk through Silero VAD or fall back to amplitude check."""
        if self._vad_model is not None:
            try:
                import torch
                tensor = torch.from_numpy(chunk.flatten()).float()
                # Pad or trim to exact chunk size
                if len(tensor) < _SILERO_CHUNK_SIZE:
                    tensor = torch.nn.functional.pad(tensor, (0, _SILERO_CHUNK_SIZE - len(tensor)))
                else:
                    tensor = tensor[:_SILERO_CHUNK_SIZE]
                with torch.no_grad():
                    prob = self._vad_model(tensor, self.sample_rate).item()
                return prob >= self.vad_threshold
            except Exception:
                pass
        # Amplitude fallback
        import numpy as np
        return float(np.abs(chunk).mean()) > self.amplitude_threshold

    def record(self) -> CapturedAudio:
        sd = _lazy_import_sounddevice()
        import numpy as np

        print(f"[rec] Listening... (max {self.max_seconds}s, stops after {self.silence_duration}s silence)")

        recorded_chunks = []
        silence_start = None
        recording_started = False
        start_time = time.time()
        stop_flag = [False]

        def callback(indata, frames, time_info, status):
            nonlocal silence_start, recording_started
            if status:
                print(f"[rec] Status: {status}")

            is_speech = self._is_speech(indata)

            if is_speech:
                recording_started = True
                silence_start = None
                recorded_chunks.append(indata.copy())
            elif recording_started:
                recorded_chunks.append(indata.copy())
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start > self.silence_duration:
                    stop_flag[0] = True

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=_SILERO_CHUNK_SIZE,
                device=sd.default.device[0],
                callback=callback,
            ):
                while not stop_flag[0]:
                    sd.sleep(50)
                    if self.max_seconds > 0 and time.time() - start_time > self.max_seconds:
                        print(f"[rec] Max duration reached ({self.max_seconds}s)")
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

        recording = np.concatenate(recorded_chunks, axis=0)
        duration = len(recording) / self.sample_rate
        print(f"[rec] Recorded {duration:.2f}s of audio")

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
