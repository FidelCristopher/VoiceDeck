import math
import sys
from typing import Optional, List, Tuple
from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QPoint, pyqtSlot
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient
from PyQt6.QtWidgets import QWidget, QApplication


class HighlightOverlay(QWidget):
    """
    Transparent, click-through, always-on-top overlay for slide annotations,
    laser pointers, in-slide text highlights, and presentation feedback.
    """

    def __init__(self, auto_fade_ms: int = 4000):
        super().__init__()
        self.auto_fade_ms = auto_fade_ms
        self.active_text: Optional[str] = None
        self.active_action: Optional[str] = None
        self.is_listening = True
        self.volume_level = 0.0

        # In-slide bounding boxes: list of normalized (x0, y0, x1, y1)
        self.highlight_boxes: List[Tuple[float, float, float, float]] = []
        self.slide_aspect_ratio: float = 16.0 / 9.0  # Default slide aspect ratio

        # Pulse animation state
        self.pulse_phase = 0.0
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(30)  # ~33 FPS
        self.anim_timer.timeout.connect(self._on_anim_tick)

        self._setup_window_properties()

        # Auto-fade timer
        self.fade_timer = QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self._clear_highlight)

    def _setup_window_properties(self):
        # Frameless, transparent, stays on top, tool window (no alt-tab clutter), click-through
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

    def _on_anim_tick(self):
        self.pulse_phase += 0.08
        if self.pulse_phase > 2 * math.pi:
            self.pulse_phase -= 2 * math.pi
        self.update()

    @pyqtSlot(str)
    def show_action(self, action_name: str):
        """Displays slide action feedback (e.g., NEXT, PREVIOUS) and clears previous slide highlights."""
        self.active_action = action_name
        self.highlight_boxes = []  # Clear highlights on slide change
        self.update()
        self.fade_timer.start(1200)

    def show_highlight(
        self,
        word: str,
        boxes: Optional[List[Tuple[float, float, float, float]]] = None,
        slide_aspect_ratio: float = 16.0 / 9.0,
    ):
        """
        Displays highlight effect.
        If boxes are provided, renders exact bounding boxes on top of slide text.
        """
        self.active_text = word
        self.highlight_boxes = boxes or []
        self.slide_aspect_ratio = slide_aspect_ratio

        if self.highlight_boxes:
            if not self.anim_timer.isActive():
                self.anim_timer.start()
        else:
            self.anim_timer.stop()

        self.update()
        self.fade_timer.start(self.auto_fade_ms)

    @pyqtSlot()
    def clear_overlay(self):
        self._clear_highlight()

    def _clear_highlight(self):
        self.active_text = None
        self.active_action = None
        self.highlight_boxes = []
        self.anim_timer.stop()
        self.update()

    def update_volume(self, rms: float):
        self.volume_level = min(1.0, rms * 15.0)
        self.update()

    def _get_slide_viewport(self) -> Tuple[float, float, float, float]:
        """
        Calculates the active presentation viewport with letterboxing / pillarboxing
        to match typical PDF fullscreen viewers.
        """
        screen_w = float(self.width())
        screen_h = float(self.height())
        screen_ratio = screen_w / max(1.0, screen_h)

        if screen_ratio > self.slide_aspect_ratio:
            # Pillarbox (black bars left and right)
            disp_h = screen_h
            disp_w = disp_h * self.slide_aspect_ratio
            offset_x = (screen_w - disp_w) / 2.0
            offset_y = 0.0
        else:
            # Letterbox (black bars top and bottom)
            disp_w = screen_w
            disp_h = disp_w / max(0.1, self.slide_aspect_ratio)
            offset_x = 0.0
            offset_y = (screen_h - disp_h) / 2.0

        return offset_x, offset_y, disp_w, disp_h

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # 1. Subtle top-right HUD indicator (Listener status & Mic pulse)
        hud_width = 160
        hud_height = 36
        hud_x = width - hud_width - 24
        hud_y = 20

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 180))
        painter.drawRoundedRect(hud_x, hud_y, hud_width, hud_height, 18, 18)

        dot_color = QColor(34, 197, 94) if self.is_listening else QColor(239, 68, 68)
        painter.setBrush(dot_color)
        painter.drawEllipse(hud_x + 14, hud_y + 12, 12, 12)

        painter.setPen(QColor(241, 245, 249))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
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

        # 3. Exact In-Slide Word Bounding Boxes (Neon Marker + Pulsing Underline)
        if self.highlight_boxes:
            offset_x, offset_y, disp_w, disp_h = self._get_slide_viewport()

            # Dynamic pulsing glow alpha
            pulse_val = 0.5 + 0.5 * math.sin(self.pulse_phase)
            fill_alpha = int(90 + 35 * pulse_val)
            glow_alpha = int(180 + 75 * pulse_val)

            for norm_box in self.highlight_boxes:
                nx0, ny0, nx1, ny1 = norm_box
                box_x = offset_x + nx0 * disp_w
                box_y = offset_y + ny0 * disp_h
                box_w = max(24.0, (nx1 - nx0) * disp_w)
                box_h = max(18.0, (ny1 - ny0) * disp_h)

                # Add a little padding around the word
                pad_x = 4.0
                pad_y = 2.0
                target_rect = QRectF(box_x - pad_x, box_y - pad_y, box_w + (pad_x * 2), box_h + (pad_y * 2))

                # Highlighter Fill: Fluorescent Neon Yellow / Amber
                painter.setPen(QPen(QColor(250, 204, 21, glow_alpha), 2.5))
                painter.setBrush(QColor(254, 240, 138, fill_alpha))
                painter.drawRoundedRect(target_rect, 6.0, 6.0)

                # Bold Underline Bar beneath the text
                underline_y = target_rect.bottom() + 2.0
                underline_pen = QPen(QColor(234, 179, 8, glow_alpha), 3.5)
                underline_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(underline_pen)
                painter.drawLine(
                    QPoint(int(target_rect.left()), int(underline_y)),
                    QPoint(int(target_rect.right()), int(underline_y)),
                )

        # 4. Floating Badge (HUD Notification)
        if self.active_text:
            matched_msg = f"✨ HIGHLIGHT: {self.active_text.upper()}"
            if self.highlight_boxes:
                matched_msg += f" ({len(self.highlight_boxes)} on slide)"

            banner_w = max(340, len(matched_msg) * 14 + 60)
            banner_h = 56
            banner_x = (width - banner_w) // 2
            banner_y = height - 100

            painter.setPen(QPen(QColor(234, 179, 8, 240), 2))
            painter.setBrush(QColor(15, 23, 42, 230))
            painter.drawRoundedRect(banner_x, banner_y, banner_w, banner_h, 14, 14)

            painter.setPen(QColor(254, 240, 138))
            painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            painter.drawText(
                QRect(banner_x, banner_y, banner_w, banner_h),
                Qt.AlignmentFlag.AlignCenter,
                matched_msg,
            )
