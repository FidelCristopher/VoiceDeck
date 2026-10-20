import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pymupdf
from rapidfuzz import fuzz

logger = logging.getLogger("voicedeck.indexer")


class SlideWord:
    def __init__(self, text: str, norm_box: Tuple[float, float, float, float], line_no: int):
        self.text = text
        self.norm_box = norm_box  # (x0, y0, x1, y1) normalized 0.0 to 1.0
        self.line_no = line_no


class SlideIndexer:
    """
    Parses PDF slides and extracts normalized word bounding boxes.
    Allows exact coordinate lookups when the user commands 'highlight <phrase>'.
    """

    def __init__(self):
        self.pdf_path: Optional[Path] = None
        self.page_count: int = 0
        self.current_page_idx: int = 0  # 0-indexed
        self.page_aspect_ratios: List[float] = []
        self.pages_words: List[List[SlideWord]] = []

    def load_pdf(self, file_path: str | Path) -> bool:
        path = Path(file_path)
        if not path.exists():
            logger.error(f"PDF file does not exist: {path}")
            return False

        try:
            doc = pymupdf.open(str(path))
            self.pdf_path = path
            self.page_count = len(doc)
            self.current_page_idx = 0
            self.pages_words = []
            self.page_aspect_ratios = []

            for page in doc:
                rect = page.rect
                page_w = rect.width
                page_h = rect.height
                self.page_aspect_ratios.append(page_w / max(1.0, page_h))

                words_data = page.get_text("words")
                # format: (x0, y0, x1, y1, word, block_no, line_no, word_no)
                words_list: List[SlideWord] = []
                for w in words_data:
                    x0, y0, x1, y1, text, _, line_no, _ = w
                    norm_box = (
                        max(0.0, x0 / page_w),
                        max(0.0, y0 / page_h),
                        min(1.0, x1 / page_w),
                        min(1.0, y1 / page_h),
                    )
                    words_list.append(SlideWord(text=text, norm_box=norm_box, line_no=line_no))

                self.pages_words.append(words_list)

            doc.close()
            logger.info(f"Loaded PDF: {path.name} with {self.page_count} pages.")
            return True
        except Exception as e:
            logger.exception(f"Failed to load PDF: {e}")
            return False

    def is_loaded(self) -> bool:
        return self.page_count > 0

    def next_page(self) -> int:
        if self.current_page_idx < self.page_count - 1:
            self.current_page_idx += 1
        return self.current_page_idx

    def prev_page(self) -> int:
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
        return self.current_page_idx

    def get_slide_vocabulary(self, page_index: Optional[int] = None) -> List[str]:
        """
        Extracts clean unique words and terms from the specified slide (or active slide)
        for dynamic grammar context biasing.
        """
        idx = self.current_page_idx if page_index is None else page_index
        if not self.is_loaded() or idx >= len(self.pages_words):
            return []

        vocab_set = set()
        for w in self.pages_words[idx]:
            clean = w.text.strip().lower().strip(".,;:?!'\"()[]{}%$#@*~`")
            if len(clean) >= 2 and clean.isalnum():
                vocab_set.add(clean)

        return sorted(list(vocab_set))

    def set_page(self, page_index: int):
        if 0 <= page_index < self.page_count:
            self.current_page_idx = page_index

    def find_phrase_boxes(
        self,
        target_phrase: str,
        threshold: float = 75.0,
    ) -> List[Tuple[float, float, float, float]]:
        """
        Searches the current slide for words or multi-word sequences matching target_phrase.
        Returns list of bounding boxes in normalized coordinates (x0, y0, x1, y1).
        """
        if not self.is_loaded() or self.current_page_idx >= len(self.pages_words):
            return []

        clean_target = target_phrase.strip().lower()
        if not clean_target:
            return []

        target_tokens = clean_target.split()
        current_words = self.pages_words[self.current_page_idx]
        matched_boxes: List[Tuple[float, float, float, float]] = []

        # 1. Single Word Exact / Fuzzy Match
        if len(target_tokens) == 1:
            query = target_tokens[0]
            for w in current_words:
                clean_word = w.text.strip().lower().strip(".,;:?!'\"()[]{}")
                # Direct match or high phonetic/string similarity
                if clean_word == query or fuzz.ratio(query, clean_word) >= threshold:
                    matched_boxes.append(w.norm_box)

            return matched_boxes

        # 2. Multi-word phrase sliding window
        window_size = len(target_tokens)
        for i in range(len(current_words) - window_size + 1):
            slice_words = current_words[i : i + window_size]
            candidate_text = " ".join(w.text.strip().lower().strip(".,;:?!'\"()[]{}") for w in slice_words)

            if fuzz.ratio(clean_target, candidate_text) >= threshold:
                # Merge bounding boxes of all words in the matched sequence
                min_x = min(w.norm_box[0] for w in slice_words)
                min_y = min(w.norm_box[1] for w in slice_words)
                max_x = max(w.norm_box[2] for w in slice_words)
                max_y = max(w.norm_box[3] for w in slice_words)
                matched_boxes.append((min_x, min_y, max_x, max_y))

        return matched_boxes
