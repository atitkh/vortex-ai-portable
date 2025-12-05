"""Simple wake word detector that works without ML dependencies."""

from __future__ import annotations

from typing import Optional

from ..interfaces import WakeWordDetector


class SimpleWakeWordDetector(WakeWordDetector):
    """
    Simple wake word detector that listens for Enter key press.
    
    This avoids the need for OpenWakeWord and heavy ML dependencies.
    Just press Enter to wake the assistant and start recording.
    
    Args:
        keyword: Wake word to display in prompt (not actually detected).
    """

    def __init__(self, keyword: str = "hey vortex") -> None:
        self.keyword = keyword

    def await_wake_word(self) -> bool:
        """Wait for user to press Enter."""
        print(f"[wake] Press ENTER when ready to speak (or type 'exit' to quit)")
        try:
            user_input = input().strip().lower()
            if user_input in ["exit", "quit", "q"]:
                print("[wake] Exiting...")
                return False
            return True
        except (KeyboardInterrupt, EOFError):
            print("\n[wake] Interrupted by user.")
            return False
