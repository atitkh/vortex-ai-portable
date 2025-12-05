"""Wake word detection for the CLI harness."""

from __future__ import annotations

from typing import Optional

from ..exceptions import WakeWordCancelled
from ..interfaces import WakeWordDetector


class KeywordWakeWordDetector(WakeWordDetector):
    """
    Blocks until the configured keyword is entered.

    Usage:
        detector = KeywordWakeWordDetector("hey vortex")
        if detector.await_wake_word():
            print("Woken!")
    """

    def __init__(self, keyword: str, *, exit_words: Optional[list[str]] = None) -> None:
        self.keyword = keyword.lower().strip()
        self.exit_words = [w.lower().strip() for w in (exit_words or ["exit", "quit"])]

    def await_wake_word(self) -> bool:
        prompt = f"Say '{self.keyword}' (or type it) to wake, or 'exit' to quit: "
        while True:
            user_input = input(prompt).strip().lower()
            if not user_input:
                continue
            if user_input in self.exit_words:
                return False
            if user_input == self.keyword:
                return True

            print(f"Unrecognized wake word '{user_input}'. Try again.")
