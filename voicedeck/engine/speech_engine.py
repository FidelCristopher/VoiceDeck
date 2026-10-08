import json
import logging
from pathlib import Path
from typing import Callable, Optional, List
from vosk import Model, KaldiRecognizer

logger = logging.getLogger("voicedeck.engine")


class SpeechEngine:
    """
    Offline Speech Recognition Engine powered by Vosk (Kaldi-based).
    Provides streaming recognition with partial & final transcripts.
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

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model path not found: {self.model_path}")

        logger.info(f"Loading Vosk model from: {self.model_path}...")
        self.model = Model(str(self.model_path))

        self._init_recognizer()

    def _init_recognizer(self):
        if self.grammar:
            # Grammar constraint boosts recognition accuracy and reduces latency to ~50ms
            grammar_json = json.dumps(self.grammar)
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate, grammar_json)
        else:
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
        if self.recognizer.AcceptWaveform(raw_bytes):
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
        self.recognizer.Reset()
