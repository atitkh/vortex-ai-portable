"""Wake word detection using openWakeWord and microphone input."""

from __future__ import annotations

import queue
from typing import Optional

import numpy as np

from ..interfaces import WakeWordDetector


class OpenWakeWordDetector(WakeWordDetector):
    """
    Blocks until the wake word is detected using openWakeWord.

    Args:
        model_path: Optional wake word model path. If omitted, openWakeWord loads defaults.
        threshold: Detection threshold between 0 and 1.
        sample_rate: Input sample rate for microphone capture.
        frame_ms: Frame size for detection in milliseconds.
    """

    def __init__(
        self,
        *,
        model_path: Optional[str] = None,
        threshold: float = 0.3,
        sample_rate: int = 16000,
        frame_ms: int = 80,
    ) -> None:
        self.model_path = model_path
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = _load_openwakeword(self.model_path)
        return self._model

    def await_wake_word(self) -> bool:
        sd = _lazy_import_sounddevice()
        frame_length = int(self.sample_rate * (self.frame_ms / 1000.0))
        q: queue.Queue[np.ndarray] = queue.Queue()
        detected_flag = [False]  # Use list to allow modification in callback

        def callback(indata, frames, time_, status):  # type: ignore[override]
            if status:
                print(f"[wake] audio status: {status}")
            if not detected_flag[0]:  # Only queue if not already detected
                q.put(indata.copy())

        print("[wake] Listening for wake word...")
        
        # Reset model state to start fresh
        self.model.reset()
        
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=frame_length,
                device=sd.default.device[0],
                callback=callback,
            ):
                while not detected_flag[0]:
                    try:
                        data = q.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    
                    audio = data[:, 0] if data.ndim > 1 else data
                    audio_int16 = (audio * 32767).astype(np.int16)
                    scores = self.model.predict(audio_int16)
                    
                    if _is_detected(scores, self.threshold):
                        print(f"[wake] Wake word detected!")
                        detected_flag[0] = True
                        self.model.reset()
                        break
            
            return detected_flag[0]
        except KeyboardInterrupt:
            print("\n[wake] Interrupted by user.")
            return False


def _is_detected(scores, threshold: float) -> bool:
    """Check if any wake word score exceeds threshold."""
    if not isinstance(scores, dict):
        return False
    
    for model_name, value in scores.items():
        # Extract scalar value from numpy types
        if hasattr(value, 'item'):
            score = float(value.item())
        elif isinstance(value, (int, float)):
            score = float(value)
        else:
            continue
        
        if score >= threshold:
            print(f"[wake] ✓ DETECTED '{model_name}' with score {score:.4f}")
            return True
    
    return False


def _lazy_import_sounddevice():
    try:
        import sounddevice as sd  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("sounddevice is required for wake word detection. Install via pip.") from exc
    return sd


def _load_openwakeword(model_path: Optional[str]):
    try:
        from openwakeword.model import Model  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("openwakeword is required for wake word detection. Install via pip.") from exc

    # Force onnxruntime inference engine
    import os
    os.environ['OPENWAKEWORD_INFERENCE_FRAMEWORK'] = 'onnx'
    
    # Download default models if needed
    print("[wake] Loading wake word models...")
    try:
        if model_path:
            return Model(wakeword_models=[model_path], inference_framework='onnx')
        else:
            # Use multiple common wake words for better detection
            # Available models: alexa, hey_mycroft, hey_jarvis, timer, weather, etc.
            return Model(inference_framework='onnx')
    except Exception as e:
        print(f"[wake] Error loading wake word model: {e}")
        raise
