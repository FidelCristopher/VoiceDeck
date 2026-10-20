import json
import logging
import threading
from pathlib import Path
from typing import Callable, Optional, List, Set
from vosk import Model, KaldiRecognizer

logger = logging.getLogger("voicedeck.engine")


class SpeechEngine:
    """
    Offline Speech Recognition Engine powered by Vosk (Kaldi-based)
    with Dynamic Context Biasing (Lexical RAG).
    """

    def __init__(
        self,
        model_path: str | Path,
        sample_rate: int = 16000,
        grammar: Optional[List[str]] = None,
    ):
        self.model_path = Path(model_path)
        self.sample_rate = sample_rate
        self.grammar = grammar
        self._lock = threading.Lock()

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model path not found: {self.model_path}")

        logger.info(f"Loading Vosk model from: {self.model_path}...")
        self.model = Model(str(self.model_path))

        self._init_recognizer()

    def _init_recognizer(self):
        with self._lock:
            if self.grammar:
                grammar_json = json.dumps(self.grammar)
                self.recognizer = KaldiRecognizer(self.model, self.sample_rate, grammar_json)
            else:
                self.recognizer = KaldiRecognizer(self.model, self.sample_rate)

            self.recognizer.SetWords(True)

    def set_dynamic_context(self, context_words: List[str], base_keywords: List[str]):
        """
        Dynamically adjusts the speech recognition grammar to favor words from
        the active slide + base control commands, drastically reducing latency and WER.
        """
        word_set: Set[str] = set()

        # Add base control words
        for kw in base_keywords:
            tokens = kw.strip().lower().split()
            for t in tokens:
                if t.isalnum():
                    word_set.add(t)

        # Add slide contextual vocabulary
        for cw in context_words:
            clean = cw.strip().lower()
            if clean.isalnum() and len(clean) >= 2:
                word_set.add(clean)

        # Vosk requires [unk] to capture words outside the grammar
        active_grammar = sorted(list(word_set))
        if "[unk]" not in active_grammar:
            active_grammar.append("[unk]")

        with self._lock:
            grammar_json = json.dumps(active_grammar)
            logger.info(f"Applying Dynamic Context Biasing ({len(active_grammar)} terms in grammar)")
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate, grammar_json)
            self.recognizer.SetWords(True)

    def reset_to_open_vocabulary(self):
        """Reverts recognizer to unrestricted open-vocabulary mode."""
        with self._lock:
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
            self.recognizer.SetWords(True)

    def process_chunk(
        self,
        raw_bytes: bytes,
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """
        Feeds raw 16-bit PCM bytes into the recognizer.
        Returns recognized final text if utterance is complete.
        """
        with self._lock:
            accepted = self.recognizer.AcceptWaveform(raw_bytes)
            if accepted:
                res = json.loads(self.recognizer.Result())
                text = res.get("text", "").strip()
                if text and on_final:
                    on_final(text)
                return text
            else:
                if on_partial:
                    partial_res = json.loads(self.recognizer.PartialResult())
                    partial_text = partial_res.get("partial", "").strip()
                    if partial_text:
                        on_partial(partial_text)
        return None

    def reset(self):
        """Resets the recognizer state."""
        with self._lock:
            self.recognizer.Reset()
