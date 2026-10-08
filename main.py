import sys
import threading
import time
import yaml
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from voicedeck.audio.capture import AudioCapture
from voicedeck.audio.vad import EnergyVAD
from voicedeck.controller.intent_parser import IntentParser
from voicedeck.controller.slide_controller import SlideController
from voicedeck.downloader import ensure_model
from voicedeck.engine.speech_engine import SpeechEngine
from voicedeck.overlay.canvas import HighlightOverlay
from voicedeck.ui.app import VoiceDeckMainWindow, WorkerSignals


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class VoiceDeckApp:
    def __init__(self):
        self.config = load_config()
        self.signals = WorkerSignals()
        self.is_running = True
        self.is_muted = False

        # Load models
        lang = self.config.get("app", {}).get("language", "en")
        models_dir = Path(__file__).parent / "models"
        self.model_path = ensure_model(language=lang, models_dir=models_dir)

        # Initialize speech & controller modules
        self.speech_engine = SpeechEngine(self.model_path)
        self.vad = EnergyVAD(
            base_threshold=self.config.get("audio", {}).get("silence_threshold_rms", 0.015)
        )
        self.intent_parser = IntentParser(self.config.get("control", {}).get("keywords", {}))
        self.slide_controller = SlideController(
            debounce_seconds=self.config.get("control", {}).get("debounce_seconds", 1.2)
        )

        # Audio capture setup
        audio_cfg = self.config.get("audio", {})
        self.audio_capture = AudioCapture(
            sample_rate=audio_cfg.get("sample_rate", 16000),
            chunk_size=audio_cfg.get("chunk_size", 4000),
            device_index=audio_cfg.get("device_index", None),
        )

        # Connect volume meter callback
        self.audio_capture.on_level_callback = self._on_audio_level

    def _on_audio_level(self, rms: float):
        self.signals.volume_changed.emit(rms)

    def _speech_worker(self):
        """Background thread reading audio and dispatching voice actions."""
        self.audio_capture.start()
        self.signals.status_changed.emit("Status: Listening for slide commands...")

        def on_partial(text: str):
            # Optional: parse partial transcript for even faster next/prev response
            intent, arg = self.intent_parser.parse(text)
            if intent == "NEXT":
                if self.slide_controller.next_slide():
                    self.signals.action_triggered.emit("NEXT")
                    self.speech_engine.reset()
            elif intent == "PREVIOUS":
                if self.slide_controller.previous_slide():
                    self.signals.action_triggered.emit("PREVIOUS")
                    self.speech_engine.reset()

        def on_final(text: str):
            self.signals.transcript_received.emit(text, True)
            intent, arg = self.intent_parser.parse(text)

            if intent == "NEXT":
                if self.slide_controller.next_slide():
                    self.signals.action_triggered.emit("NEXT")
            elif intent == "PREVIOUS":
                if self.slide_controller.previous_slide():
                    self.signals.action_triggered.emit("PREVIOUS")
            elif intent == "HIGHLIGHT":
                target = arg or "Focus"
                self.signals.highlight_triggered.emit(target)
            elif intent == "CLEAR":
                # Clear active overlay
                pass

        while self.is_running:
            chunk = self.audio_capture.read_chunk(timeout=0.2)
            if chunk is None or self.is_muted:
                continue

            # Process chunk through speech engine
            self.speech_engine.process_chunk(
                chunk,
                on_partial=on_partial,
                on_final=on_final,
            )

    def start(self):
        qt_app = QApplication(sys.argv)

        # Setup GUI window
        main_window = VoiceDeckMainWindow(self.config, self.signals)
        main_window.show()

        # Setup Transparent Overlay
        overlay = HighlightOverlay()
        overlay.show()

        # Wire overlay to signals
        self.signals.action_triggered.connect(overlay.show_action)
        self.signals.highlight_triggered.connect(overlay.show_highlight)
        self.signals.volume_changed.connect(overlay.update_volume)

        # Start speech thread
        worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        worker_thread.start()

        # Run Qt Event Loop
        exit_code = qt_app.exec()

        # Cleanup
        self.is_running = False
        self.audio_capture.stop()
        sys.exit(exit_code)


if __name__ == "__main__":
    app = VoiceDeckApp()
    app.start()
