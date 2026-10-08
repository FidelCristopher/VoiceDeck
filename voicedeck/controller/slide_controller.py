import time
import logging
from typing import Optional, Callable
from pynput.keyboard import Controller, Key

logger = logging.getLogger("voicedeck.controller")


class SlideController:
    """
    Simulates keyboard events to advance or retreat slides in any presentation software
    (PowerPoint, Google Slides, Keynote, PDF viewers, Reveal.js).
    """

    def __init__(self, debounce_seconds: float = 1.2):
        self.keyboard = Controller()
        self.debounce_seconds = debounce_seconds
        self.last_action_time = 0.0
        self.on_action_callback: Optional[Callable[[str], None]] = None

    def _can_trigger(self) -> bool:
        return (time.time() - self.last_action_time) >= self.debounce_seconds

    def next_slide(self) -> bool:
        """Advance to next slide (Right Arrow)."""
        if not self._can_trigger():
            return False

        logger.info("[SlideController] -> NEXT SLIDE")
        self.keyboard.press(Key.right)
        self.keyboard.release(Key.right)
        self.last_action_time = time.time()

        if self.on_action_callback:
            self.on_action_callback("NEXT")
        return True

    def previous_slide(self) -> bool:
        """Go back to previous slide (Left Arrow)."""
        if not self._can_trigger():
            return False

        logger.info("[SlideController] <- PREVIOUS SLIDE")
        self.keyboard.press(Key.left)
        self.keyboard.release(Key.left)
        self.last_action_time = time.time()

        if self.on_action_callback:
            self.on_action_callback("PREVIOUS")
        return True

    def toggle_presentation(self):
        """Start or present slide (F5)."""
        self.keyboard.press(Key.f5)
        self.keyboard.release(Key.f5)
