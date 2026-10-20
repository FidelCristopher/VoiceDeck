import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QFileDialog,
    QSpinBox,
)

from voicedeck.audio.capture import AudioCapture


class WorkerSignals(QObject):
    transcript_received = pyqtSignal(str, bool)  # text, is_final
    action_triggered = pyqtSignal(str)          # NEXT, PREVIOUS
    highlight_triggered = pyqtSignal(str, list, float)  # target_word, boxes, aspect_ratio
    volume_changed = pyqtSignal(float)          # rms level
    status_changed = pyqtSignal(str)
    slide_page_changed = pyqtSignal(int, int)   # current_page_idx, total_pages


class VoiceDeckMainWindow(QMainWindow):
    def __init__(self, config: Dict[str, Any], signals: WorkerSignals, on_load_pdf_cb=None, on_slide_change_cb=None):
        super().__init__()
        self.config = config
        self.signals = signals
        self.on_load_pdf_cb = on_load_pdf_cb
        self.on_slide_change_cb = on_slide_change_cb

        self.setWindowTitle(f"VoiceDeck v{config.get('app', {}).get('version', '1.0.0')} - Pitch Assistant")
        self.resize(560, 680)
        self.setMinimumSize(480, 560)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Title & Active/Mute toggle
        header_layout = QHBoxLayout()
        title_label = QLabel("VoiceDeck Studio")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0284c7;")
        self.mute_btn = QPushButton("Active (Click to Mute)")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setStyleSheet(
            "QPushButton { background-color: #22c55e; color: white; font-weight: bold; border-radius: 6px; padding: 6px 14px; }"
            "QPushButton:checked { background-color: #ef4444; }"
        )
        self.mute_btn.toggled.connect(self._on_mute_toggled)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.mute_btn)
        main_layout.addLayout(header_layout)

        # 1. Slide Deck / PDF Integration Group
        pdf_group = QGroupBox("Slide Deck Integration (Precise In-Slide Highlighter)")
        pdf_layout = QVBoxLayout(pdf_group)

        pdf_top_row = QHBoxLayout()
        self.btn_load_pdf = QPushButton("Load Presentation PDF...")
        self.btn_load_pdf.setStyleSheet(
            "background-color: #334155; color: #f8fafc; font-weight: 600; padding: 5px 12px; border-radius: 5px;"
        )
        self.btn_load_pdf.clicked.connect(self._on_choose_pdf)
        self.lbl_pdf_name = QLabel("No PDF loaded (HUD mode only)")
        self.lbl_pdf_name.setStyleSheet("color: #94a3b8; font-style: italic;")

        pdf_top_row.addWidget(self.btn_load_pdf)
        pdf_top_row.addWidget(self.lbl_pdf_name, 1)
        pdf_layout.addLayout(pdf_top_row)

        # Slide page tracker controls
        page_row = QHBoxLayout()
        self.lbl_current_slide = QLabel("Current Slide:")
        self.spin_page = QSpinBox()
        self.spin_page.setRange(1, 1)
        self.spin_page.setEnabled(False)
        self.spin_page.valueChanged.connect(self._on_spin_page_changed)
        self.lbl_total_pages = QLabel("of 1")

        self.btn_sync_prev = QPushButton("Prev")
        self.btn_sync_next = QPushButton("Next")
        self.btn_sync_prev.setEnabled(False)
        self.btn_sync_next.setEnabled(False)
        self.btn_sync_prev.clicked.connect(lambda: self.signals.action_triggered.emit("PREVIOUS"))
        self.btn_sync_next.clicked.connect(lambda: self.signals.action_triggered.emit("NEXT"))

        page_row.addWidget(self.lbl_current_slide)
        page_row.addWidget(self.spin_page)
        page_row.addWidget(self.lbl_total_pages)
        page_row.addStretch()
        page_row.addWidget(self.btn_sync_prev)
        page_row.addWidget(self.btn_sync_next)
        pdf_layout.addLayout(page_row)

        main_layout.addWidget(pdf_group)

        # 2. Audio Device Selection & Level Meter
        audio_group = QGroupBox("Microphone & Audio Input")
        audio_layout = QVBoxLayout(audio_group)

        dev_row = QHBoxLayout()
        dev_label = QLabel("Device:")
        self.device_combo = QComboBox()
        self._populate_audio_devices()
        dev_row.addWidget(dev_label)
        dev_row.addWidget(self.device_combo, 1)
        audio_layout.addLayout(dev_row)

        meter_row = QHBoxLayout()
        meter_label = QLabel("Level:")
        self.volume_bar = QProgressBar()
        self.volume_bar.setRange(0, 100)
        self.volume_bar.setValue(0)
        self.volume_bar.setTextVisible(False)
        self.volume_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #38bdf8; border-radius: 3px; }"
        )
        meter_row.addWidget(meter_label)
        meter_row.addWidget(self.volume_bar)
        audio_layout.addLayout(meter_row)

        main_layout.addWidget(audio_group)

        # 3. Live Speech Activity Log
        log_group = QGroupBox("Live Voice Transcripts & Actions")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color: #0f172a; color: #e2e8f0; font-family: Consolas, monospace; font-size: 11px; border-radius: 6px;"
        )
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group, 1)

        # Status Bar
        self.status_label = QLabel("Status: Initializing Voice Pipeline...")
        self.status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        main_layout.addWidget(self.status_label)

    def _populate_audio_devices(self):
        devices = AudioCapture.list_input_devices()
        self.device_combo.addItem("Default System Microphone", None)
        for dev in devices:
            self.device_combo.addItem(f"[{dev['index']}] {dev['name']}", dev['index'])

    def _connect_signals(self):
        self.signals.transcript_received.connect(self._append_transcript)
        self.signals.action_triggered.connect(self._on_action_log)
        self.signals.highlight_triggered.connect(self._on_highlight_log)
        self.signals.volume_changed.connect(self._update_volume_bar)
        self.signals.status_changed.connect(self.status_label.setText)
        self.signals.slide_page_changed.connect(self._update_page_tracker)

    def _on_choose_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Presentation PDF",
            "",
            "PDF Files (*.pdf)",
        )
        if file_path and self.on_load_pdf_cb:
            self.on_load_pdf_cb(file_path)

    def set_pdf_loaded(self, filename: str, total_pages: int, vocab_count: int = 0):
        self.lbl_pdf_name.setText(f"{filename} (Dynamic Context: {vocab_count} terms)")
        self.lbl_pdf_name.setStyleSheet("color: #22c55e; font-weight: bold;")
        self.spin_page.setEnabled(True)
        self.spin_page.setRange(1, total_pages)
        self.spin_page.setValue(1)
        self.lbl_total_pages.setText(f"of {total_pages}")
        self.btn_sync_prev.setEnabled(True)
        self.btn_sync_next.setEnabled(True)
        self.log_text.append(f"<span style='color: #22c55e;'>Loaded '{filename}' ({total_pages} slides). Context Biasing Active.</span>")

    def _update_page_tracker(self, current_page_idx: int, total_pages: int):
        self.spin_page.blockSignals(True)
        self.spin_page.setValue(current_page_idx + 1)
        self.spin_page.blockSignals(False)
        self.lbl_total_pages.setText(f"of {total_pages}")

    def _on_spin_page_changed(self, val: int):
        if self.on_slide_change_cb:
            self.on_slide_change_cb(val - 1)

    def _append_transcript(self, text: str, is_final: bool):
        if is_final:
            self.log_text.append(f"<span style='color: #a78bfa;'>[HEARD]:</span> {text}")

    def _on_action_log(self, action: str):
        self.log_text.append(f"<span style='color: #38bdf8; font-weight: bold;'>[TRIGGER]: {action} SLIDE</span>")

    def _on_highlight_log(self, word: str, boxes: list, aspect_ratio: float):
        box_count = len(boxes)
        if box_count > 0:
            self.log_text.append(
                f"<span style='color: #facc15; font-weight: bold;'>[HIGHLIGHT]: '{word}' (Targeted {box_count} match on slide)</span>"
            )
        else:
            self.log_text.append(
                f"<span style='color: #facc15; font-weight: bold;'>[HIGHLIGHT]: '{word}' (HUD badge)</span>"
            )

    def _update_volume_bar(self, rms: float):
        percent = int(min(1.0, rms * 15.0) * 100)
        self.volume_bar.setValue(percent)

    def _on_mute_toggled(self, checked: bool):
        if checked:
            self.mute_btn.setText("Muted (Speech Paused)")
            self.status_label.setText("Status: Muted - Voice recognition paused.")
        else:
            self.mute_btn.setText("Active (Click to Mute)")
            self.status_label.setText("Status: Listening...")
