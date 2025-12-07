"""Audio feedback sounds for wake word detection and recording states."""

from __future__ import annotations

import numpy as np
from typing import Optional


def play_beep(frequency: int = 800, duration: float = 0.15, sample_rate: int = 22050, volume: float = 0.8) -> None:
    """Play a simple beep sound.
    
    Args:
        frequency: Tone frequency in Hz
        duration: Duration in seconds
        sample_rate: Audio sample rate
        volume: Volume level (0.0 to 1.0)
    """
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        print("[audio] sounddevice not available")
        return
    
    print(f"[audio] Generating beep: {frequency}Hz, {duration}s, vol={volume}")
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Use sine wave for smooth sound
    tone = np.sin(frequency * 2 * np.pi * t)
    
    # Apply smooth envelope
    fade_samples = int(sample_rate * 0.05)  # 50ms fade
    if fade_samples > 0 and len(tone) > fade_samples * 2:
        fade_in = np.linspace(0, 1, fade_samples) ** 2  # Smooth curve
        fade_out = np.linspace(1, 0, fade_samples) ** 2
        tone[:fade_samples] *= fade_in
        tone[-fade_samples:] *= fade_out
    
    # Apply volume
    tone = tone * volume
    
    print(f"[audio] Tone range: min={tone.min():.3f}, max={tone.max():.3f}, mean={np.abs(tone).mean():.3f}")
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True)
    print(f"[audio] Tone playback complete")


def play_wake_sound() -> None:
    """Play a rising tone to indicate wake word detected (like Google Assistant)."""
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        print("[audio] sounddevice not available")
        return
    
    sample_rate = 22050
    duration = 0.4
    
    print("[audio] Generating wake sound...")
    # Generate smooth rising sweep from 400Hz to 800Hz
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Smooth frequency sweep
    freq_start = 400
    freq_end = 800
    phase = 0
    tone = []
    for i in range(len(t)):
        freq = freq_start + (freq_end - freq_start) * (i / len(t))
        phase += 2 * np.pi * freq / sample_rate
        tone.append(np.sin(phase))
    
    tone = np.array(tone)
    
    # Apply smooth amplitude envelope
    envelope = np.concatenate([
        np.linspace(0, 0.8, len(t)//3),  # Fade in
        np.ones(len(t)//3) * 0.8,         # Sustain
        np.linspace(0.8, 0, len(t)//3)    # Fade out
    ])
    if len(envelope) < len(tone):
        envelope = np.concatenate([envelope, [0]])
    tone = tone * envelope[:len(tone)]
    
    print(f"[audio] Tone range: min={tone.min():.3f}, max={tone.max():.3f}")
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True)
    print(f"[audio] Wake tone complete")


def play_listening_end_sound() -> None:
    """Play a falling tone to indicate recording stopped."""
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        print("[audio] sounddevice not available")
        return
    
    sample_rate = 22050
    duration = 0.2
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    print("[audio] Generating end sound...")
    # Falling frequency from 1000Hz to 600Hz
    freq_start = 1000
    freq_end = 600
    phase = 0
    tone = []
    for i, time in enumerate(t):
        freq = freq_start + (freq_end - freq_start) * (i / len(t))
        phase += 2 * np.pi * freq / sample_rate
        tone.append(np.sin(phase))
    
    tone = np.array(tone)
    
    # Apply envelope with higher volume
    envelope = np.linspace(1.0, 0.5, len(t))
    tone = tone * envelope
    
    print(f"[audio] Playing end tone with {len(tone)} samples...")
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True)
    print(f"[audio] End tone complete")


def play_double_beep() -> None:
    """Play falling tone to indicate listening stopped (like Alexa)."""
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        print("[audio] sounddevice not available")
        return
    
    sample_rate = 22050
    duration = 0.35
    
    print("[audio] Playing end sound...")
    # Generate smooth falling sweep from 800Hz to 500Hz
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Smooth frequency sweep downward
    freq_start = 800
    freq_end = 500
    phase = 0
    tone = []
    for i in range(len(t)):
        freq = freq_start + (freq_end - freq_start) * (i / len(t))
        phase += 2 * np.pi * freq / sample_rate
        tone.append(np.sin(phase))
    
    tone = np.array(tone)
    
    # Apply smooth amplitude envelope
    envelope = np.concatenate([
        np.linspace(0, 0.75, len(t)//4),  # Quick fade in
        np.ones(len(t)//4) * 0.75,        # Sustain
        np.linspace(0.75, 0, len(t)//2)   # Long fade out
    ])
    if len(envelope) < len(tone):
        envelope = np.concatenate([envelope, [0]])
    tone = tone * envelope[:len(tone)]
    
    print(f"[audio] Tone range: min={tone.min():.3f}, max={tone.max():.3f}")
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True)
    print("[audio] End sound complete")
