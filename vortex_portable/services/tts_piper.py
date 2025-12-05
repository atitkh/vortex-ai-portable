"""Piper TTS adapter that calls the `piper` CLI and plays audio via sounddevice."""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional

import numpy as np

from ..interfaces import TextToSpeech


class PiperTextToSpeech(TextToSpeech):
    """
    Text-to-speech using the `piper` command-line binary.

    Args:
        model_path: Path to a Piper `.onnx` model.
        binary_path: Piper executable name or path (default: "piper").
        speaker: Optional speaker ID/name, passed via `--speaker`.
        sample_rate: Playback sample rate (Hz).

    Notes:
        - Requires the Piper binary in PATH (or provide binary_path).
        - Requires `sounddevice` for playback.
        - The Piper model determines the appropriate sample rate; ensure `sample_rate`
          matches your model or leave at the model default if known.
    """

    def __init__(
        self,
        *,
        model_path: str,
        binary_path: str = "piper",
        speaker: Optional[str] = None,
        sample_rate: int = 16000,
    ) -> None:
        if not shutil.which(binary_path):
            raise RuntimeError(
                f"Piper binary '{binary_path}' not found. Install Piper and adjust binary_path or PATH."
            )
        self.model_path = model_path
        self.binary_path = binary_path
        self.speaker = speaker
        self.sample_rate = sample_rate

    def speak(self, text: str) -> None:
        if not text.strip():
            return

        sd = _lazy_import_sounddevice()
        cmd = [
            self.binary_path,
            "--model",
            self.model_path,
            "--output-raw",
        ]
        if self.speaker:
            cmd.extend(["--speaker", self.speaker])

        try:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - external tool
            raise RuntimeError(
                f"Piper failed (exit {exc.returncode}): {exc.stderr.decode('utf-8', errors='ignore')}"
            ) from exc

        raw = proc.stdout
        if not raw:
            raise RuntimeError("Piper produced no audio output.")

        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(pcm, samplerate=self.sample_rate)
        sd.wait()


def _lazy_import_sounddevice():
    try:
        import sounddevice as sd  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("sounddevice is required for Piper playback. Install via pip.") from exc
    return sd
