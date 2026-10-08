import sys
from typing import Optional
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, pyqtSlot
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt6.QtWidgets import QWidget, QApplication


class HighlightOverlay(QWidget):
    """
    Transparent, click-through, always-on-top overlay for slide annotations and visual feedback.
    """

    def __init__(self, auto_fade_ms: int = 3500):
        super().__init__()
        self.auto_fade_ms = auto_fade_ms
        self.active_text: Optional[str] = None
        self.active_action: Optional[str] = None
        self.status_text: str = "VoiceDeck Ready"
        self.is_listening = True
        self.volume_level = 0.0

        self._setup_window_properties()

        # Fade timer
        self.fade_timer = QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self._clear_highlight)

    def _setup_window_properties(self):
        # Frameless, transparent, stays on top, tool window (no alt-tab clutter)
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForInput, True)

        # Full screen coverage
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

    @pyqtSlot(str)
    def show_action(self, action_name: str):
        """Displays slide action feedback (e.g., NEXT, PREVIOUS)."""
        self.active_action = action_name
        self.update()
        self.fade_timer.start(1200)

    @pyqtSlot(str)
    def show_highlight(self, word: str):
        """Displays highlight effect for the requested word."""
        self.active_text = word
        self.update()
        self.fade_timer.start(self.auto_fade_ms)

    @pyqtSlot()
    def clear_overlay(self):
        self._clear_highlight()

    def _clear_highlight(self):
        self.active_text = None
        self.active_action = None
        self.update()

    def update_volume(self, rms: float):
        self.volume_level = min(1.0, rms * 15.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # 1. Subtle top-right HUD indicator (Listener status & Volume meter)
        hud_width = 160
        hud_height = 36
        hud_x = width - hud_width - 24
        hud_y = 20

        # HUD pill background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(18, 18, 24, 180))
        painter.drawRoundedRect(hud_x, hud_y, hud_width, hud_height, 18, 18)

        # Pulsing mic dot
        dot_color = QColor(34, 197, 94) if self.is_listening else QColor(239, 68, 68)
        painter.setBrush(dot_color)
        painter.drawEllipse(hud_x + 14, hud_y + 12, 12, 12)

        # Text in HUD
        painter.setPen(QColor(240, 240, 240))
        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(
            QRect(hud_x + 34, hud_y, hud_width - 44, hud_height),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "Listening..." if self.is_listening else "Muted",
        )

        # 2. Action badge (Next / Prev notification)
        if self.active_action:
            badge_w = 220
            badge_h = 56
            badge_x = (width - badge_w) // 2
            badge_y = 80

            painter.setPen(QPen(QColor(59, 130, 246, 220), 2))
            painter.setBrush(QColor(15, 23, 42, 220))
            painter.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, 16, 16)

            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            arrow = "➡ " if self.active_action == "NEXT" else "⬅ "
            painter.drawText(
                QRect(badge_x, badge_y, badge_w, badge_h),
                Qt.AlignmentFlag.AlignCenter,
                f"{arrow} {self.active_action} SLIDE",
            )

        # 3. Dynamic Highlight Banner / Floating Marker
        if self.active_text:
            text_str = f"✨ {self.active_text.upper()}"
            banner_w = max(320, len(text_str) * 18 + 60)
            banner_h = 64
            banner_x = (width - banner_w) // 2
            banner_y = height - 120

            # Glowing neon yellow-amber background with soft border
            painter.setPen(QPen(QColor(234, 179, 8, 255), 2))
            painter.setBrush(QColor(254, 240, 138, 230))
            painter.drawRoundedRect(banner_x, banner_y, banner_w, banner_h, 14, 14)

            # High-contrast bold typography for stage readability
            painter.setPen(QColor(113, 63, 18))
            painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            painter.drawText(
                QRect(banner_x, banner_y, banner_w, banner_h),
                Qt.AlignmentFlag.AlignCenter,
                text_str,
            )
