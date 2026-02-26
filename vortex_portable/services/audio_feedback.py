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
    
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True, device=sd.default.device[1])


def play_wake_sound() -> None:
    """Play a rising tone to indicate wake word detected (like Google Assistant)."""
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        print("[audio] sounddevice not available")
        return
    
    sample_rate = 22050
    duration = 0.4
    
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
    
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True, device=sd.default.device[1])


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
    
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True, device=sd.default.device[1])


def play_double_beep() -> None:
    """Play falling tone to indicate listening stopped (like Alexa)."""
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        print("[audio] sounddevice not available")
        return
    
    sample_rate = 22050
    duration = 0.35
    
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
    
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True, device=sd.default.device[1])


def play_thinking_sound() -> None:
    """Play a subtle pulsing tone to indicate AI is thinking/processing."""
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        return
    
    sample_rate = 22050
    duration = 0.3
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Gentle pulsing tone at 600Hz
    tone = np.sin(600 * 2 * np.pi * t)
    
    # Pulsing amplitude (2 pulses)
    pulse = 0.5 + 0.3 * np.sin(8 * np.pi * t)
    
    # Apply envelope
    envelope = np.concatenate([
        np.linspace(0, 1, len(t)//4),
        np.ones(len(t)//2),
        np.linspace(1, 0, len(t)//4)
    ])[:len(t)]
    
    tone = tone * pulse * envelope * 0.4
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True, device=sd.default.device[1])


def play_speaking_start_sound() -> None:
    """Play a quick ascending chime to indicate assistant is about to speak."""
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        return
    
    sample_rate = 22050
    duration = 0.15
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Quick rising tone from 700Hz to 900Hz
    freq_start = 700
    freq_end = 900
    phase = 0
    tone = []
    for i in range(len(t)):
        freq = freq_start + (freq_end - freq_start) * (i / len(t))
        phase += 2 * np.pi * freq / sample_rate
        tone.append(np.sin(phase))
    
    tone = np.array(tone)
    
    # Quick fade in/out
    envelope = np.concatenate([
        np.linspace(0, 0.5, len(t)//3),
        np.ones(len(t)//3) * 0.5,
        np.linspace(0.5, 0, len(t)//3)
    ])[:len(t)]
    
    tone = tone * envelope
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True, device=sd.default.device[1])


def play_error_sound() -> None:
    """Play a descending error tone."""
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        return
    
    sample_rate = 22050
    duration = 0.4
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Descending tone from 600Hz to 300Hz
    freq_start = 600
    freq_end = 300
    phase = 0
    tone = []
    for i in range(len(t)):
        freq = freq_start + (freq_end - freq_start) * (i / len(t))
        phase += 2 * np.pi * freq / sample_rate
        tone.append(np.sin(phase))
    
    tone = np.array(tone)
    
    # Apply envelope
    envelope = np.linspace(0.7, 0, len(t))
    tone = tone * envelope
    sd.play(tone.astype(np.float32), samplerate=sample_rate, blocking=True, device=sd.default.device[1])
