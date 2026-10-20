import sys
import threading
import time
import yaml
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import QApplication

from voicedeck.audio.capture import AudioCapture
from voicedeck.audio.vad import EnergyVAD
from voicedeck.controller.intent_parser import IntentParser
from voicedeck.controller.slide_controller import SlideController
from voicedeck.downloader import ensure_model
from voicedeck.engine.speech_engine import SpeechEngine
from voicedeck.indexer.slide_indexer import SlideIndexer
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
        self.slide_indexer = SlideIndexer()

        # Cache base keywords for grammar biasing
        self.base_keywords: List[str] = []
        for kw_list in self.config.get("control", {}).get("keywords", {}).values():
            self.base_keywords.extend(kw_list)
        self.base_keywords.extend(["clear", "hapus", "hilangkan"])

        # Audio capture setup
        audio_cfg = self.config.get("audio", {})
        self.audio_capture = AudioCapture(
            sample_rate=audio_cfg.get("sample_rate", 16000),
            chunk_size=audio_cfg.get("chunk_size", 4000),
            device_index=audio_cfg.get("device_index", None),
        )

        self.audio_capture.on_level_callback = self._on_audio_level

    def _on_audio_level(self, rms: float):
        self.signals.volume_changed.emit(rms)

    def _apply_slide_context(self, page_index: int):
        """Dynamic Context Biasing: updates recognition grammar to active slide vocabulary."""
        if not self.config.get("context_biasing", {}).get("enabled", True):
            return

        if self.slide_indexer.is_loaded():
            slide_vocab = self.slide_indexer.get_slide_vocabulary(page_index)
            self.speech_engine.set_dynamic_context(slide_vocab, self.base_keywords)

    def on_load_pdf(self, file_path: str):
        if self.slide_indexer.load_pdf(file_path):
            filename = Path(file_path).name
            total_pages = self.slide_indexer.page_count
            vocab = self.slide_indexer.get_slide_vocabulary(0)
            self._apply_slide_context(0)
            self.main_window.set_pdf_loaded(filename, total_pages, len(vocab))

    def on_slide_change(self, page_index: int):
        self.slide_indexer.set_page(page_index)
        self._apply_slide_context(page_index)

    def _trigger_next(self):
        if self.slide_controller.next_slide():
            self.signals.action_triggered.emit("NEXT")
            if self.slide_indexer.is_loaded():
                curr = self.slide_indexer.next_page()
                self._apply_slide_context(curr)
                self.signals.slide_page_changed.emit(curr, self.slide_indexer.page_count)
            self.speech_engine.reset()

    def _trigger_prev(self):
        if self.slide_controller.previous_slide():
            self.signals.action_triggered.emit("PREVIOUS")
            if self.slide_indexer.is_loaded():
                curr = self.slide_indexer.prev_page()
                self._apply_slide_context(curr)
                self.signals.slide_page_changed.emit(curr, self.slide_indexer.page_count)
            self.speech_engine.reset()

    def _trigger_highlight(self, target_word: str):
        target = target_word or "focus"
        boxes = []
        aspect_ratio = 16.0 / 9.0

        if self.slide_indexer.is_loaded():
            boxes = self.slide_indexer.find_phrase_boxes(target)
            idx = self.slide_indexer.current_page_idx
            if idx < len(self.slide_indexer.page_aspect_ratios):
                aspect_ratio = self.slide_indexer.page_aspect_ratios[idx]

        self.signals.highlight_triggered.emit(target, boxes, aspect_ratio)

    def _speech_worker(self):
        """Background thread reading audio and dispatching voice actions."""
        self.audio_capture.start()
        self.signals.status_changed.emit("Status: Listening for slide commands...")

        def on_partial(text: str):
            intent, arg = self.intent_parser.parse(text)
            if intent == "NEXT":
                self._trigger_next()
            elif intent == "PREVIOUS":
                self._trigger_prev()

        def on_final(text: str):
            self.signals.transcript_received.emit(text, True)
            intent, arg = self.intent_parser.parse(text)

            if intent == "NEXT":
                self._trigger_next()
            elif intent == "PREVIOUS":
                self._trigger_prev()
            elif intent == "HIGHLIGHT":
                self._trigger_highlight(arg or "highlight")
            elif intent == "CLEAR":
                self.signals.action_triggered.emit("CLEAR")
            else:
                # Proactive Auto-Highlight check if enabled in config
                if (
                    self.config.get("context_biasing", {}).get("auto_highlight", False)
                    and self.slide_indexer.is_loaded()
                ):
                    min_len = self.config.get("context_biasing", {}).get("min_term_length", 3)
                    words = [w for w in text.split() if len(w) >= min_len]
                    for w in words:
                        boxes = self.slide_indexer.find_phrase_boxes(w)
                        if boxes:
                            self._trigger_highlight(w)
                            break

        while self.is_running:
            chunk = self.audio_capture.read_chunk(timeout=0.2)
            if chunk is None or self.is_muted:
                continue

            self.speech_engine.process_chunk(
                chunk,
                on_partial=on_partial,
                on_final=on_final,
            )

    def start(self):
        qt_app = QApplication(sys.argv)

        # Setup GUI window
        self.main_window = VoiceDeckMainWindow(
            self.config,
            self.signals,
            on_load_pdf_cb=self.on_load_pdf,
            on_slide_change_cb=self.on_slide_change,
        )
        self.main_window.show()

        # Setup Transparent Overlay
        overlay = HighlightOverlay(
            auto_fade_ms=int(self.config.get("overlay", {}).get("auto_fade_seconds", 4.0) * 1000)
        )
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
