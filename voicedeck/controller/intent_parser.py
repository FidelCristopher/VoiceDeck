import re
from typing import Dict, List, Optional, Tuple


class IntentParser:
    """
    Parses speech transcripts to extract intent (NEXT, PREVIOUS, HIGHLIGHT, CLEAR)
    and any target arguments (e.g. target keyword to highlight).
    """

    def __init__(self, config_keywords: Dict[str, List[str]]):
        self.next_keywords = [k.lower() for k in config_keywords.get("next", ["next", "lanjut"])]
        self.prev_keywords = [k.lower() for k in config_keywords.get("previous", ["back", "kembali"])]
        self.highlight_keywords = [
            k.lower() for k in config_keywords.get("highlight", ["highlight", "sorot", "tandai"])
        ]
        self.clear_keywords = ["clear", "hapus", "hilangkan", "clear highlight"]

    def parse(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parses text and returns (intent, argument).
        Intents: 'NEXT', 'PREVIOUS', 'HIGHLIGHT', 'CLEAR', or None.
        """
        cleaned = text.strip().lower()
        if not cleaned:
            return None, None

        # Check Clear command
        for kw in self.clear_keywords:
            if kw in cleaned:
                return "CLEAR", None

        # Check Highlight command
        for kw in self.highlight_keywords:
            pattern = rf"\b{re.escape(kw)}\b\s*(.*)"
            match = re.search(pattern, cleaned)
            if match:
                target_word = match.group(1).strip()
                # Remove common filler words
                target_word = re.sub(r"^(kata|bagian|angka|poin|text|the word)\s+", "", target_word)
                return "HIGHLIGHT", target_word if target_word else "highlight"

        # Check Next command
        for kw in self.next_keywords:
            if re.search(rf"\b{re.escape(kw)}\b", cleaned):
                return "NEXT", None

        # Check Previous command
        for kw in self.prev_keywords:
            if re.search(rf"\b{re.escape(kw)}\b", cleaned):
                return "PREVIOUS", None

        return None, None
