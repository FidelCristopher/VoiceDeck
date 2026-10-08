import sys
import threading
from typing import Dict, Any
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
    QSlider,
    QGroupBox,
)

from voicedeck.audio.capture import AudioCapture


class WorkerSignals(QObject):
    transcript_received = pyqtSignal(str, bool)  # text, is_final
    action_triggered = pyqtSignal(str)          # NEXT, PREVIOUS
    highlight_triggered = pyqtSignal(str)       # target_word
    volume_changed = pyqtSignal(float)          # rms level
    status_changed = pyqtSignal(str)


class VoiceDeckMainWindow(QMainWindow):
    def __init__(self, config: Dict[str, Any], signals: WorkerSignals):
        super().__init__()
        self.config = config
        self.signals = signals

        self.setWindowTitle(f"VoiceDeck v{config.get('app', {}).get('version', '1.0.0')} - Pitch Assistant")
        self.resize(520, 620)
        self.setMinimumSize(450, 500)

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Title / Pitch status header
        header_layout = QHBoxLayout()
        title_label = QLabel("🎤 VoiceDeck Studio")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #0284c7;")
        self.mute_btn = QPushButton("🔴 Active (Click to Mute)")
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

        # 1. Audio Device Selection
        audio_group = QGroupBox("Microphone & Audio Input")
        audio_layout = QVBoxLayout(audio_group)

        dev_row = QHBoxLayout()
        dev_label = QLabel("Device:")
        self.device_combo = QComboBox()
        self._populate_audio_devices()
        dev_row.addWidget(dev_label)
        dev_row.addWidget(self.device_combo, 1)
        audio_layout.addLayout(dev_row)

        # VU Volume Meter
        meter_row = QHBoxLayout()
        meter_label = QLabel("Level:")
        self.volume_bar = QProgressBar()
        self.volume_bar.setRange(0, 100)
        self.volume_bar.setValue(0)
        self.volume_bar.setTextVisible(False)
        self.volume_bar.setStyleSheet(
            "QProgressBar::chunk { background-color: #3b82f6; border-radius: 3px; }"
        )
        meter_row.addWidget(meter_label)
        meter_row.addWidget(self.volume_bar)
        audio_layout.addLayout(meter_row)

        main_layout.addWidget(audio_group)

        # 2. Controls & Testing Sandbox
        test_group = QGroupBox("Quick Testing / Manual Override")
        test_layout = QHBoxLayout(test_group)

        self.btn_test_prev = QPushButton("⬅ Prev Slide")
        self.btn_test_next = QPushButton("➡ Next Slide")
        self.btn_test_hl = QPushButton("✨ Highlight Demo")

        self.btn_test_prev.clicked.connect(lambda: self.signals.action_triggered.emit("PREVIOUS"))
        self.btn_test_next.clicked.connect(lambda: self.signals.action_triggered.emit("NEXT"))
        self.btn_test_hl.clicked.connect(lambda: self.signals.highlight_triggered.emit("Key Traction Metric"))

        test_layout.addWidget(self.btn_test_prev)
        test_layout.addWidget(self.btn_test_next)
        test_layout.addWidget(self.btn_test_hl)
        main_layout.addWidget(test_group)

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

    def _append_transcript(self, text: str, is_final: bool):
        if is_final:
            self.log_text.append(f"<span style='color: #a78bfa;'>🗣 [Heard]:</span> {text}")
        else:
            # could display transient partial transcript if desired
            pass

    def _on_action_log(self, action: str):
        self.log_text.append(f"<span style='color: #38bdf8; font-weight: bold;'>⚡ [TRIGGER]: {action} SLIDE</span>")

    def _on_highlight_log(self, word: str):
        self.log_text.append(f"<span style='color: #facc15; font-weight: bold;'>💡 [HIGHLIGHT]: '{word}'</span>")

    def _update_volume_bar(self, rms: float):
        percent = int(min(1.0, rms * 15.0) * 100)
        self.volume_bar.setValue(percent)

    def _on_mute_toggled(self, checked: bool):
        if checked:
            self.mute_btn.setText("⏸ Muted (Speech Paused)")
            self.status_label.setText("Status: Muted - Voice recognition paused.")
        else:
            self.mute_btn.setText("🔴 Active (Click to Mute)")
            self.status_label.setText("Status: Listening...")
