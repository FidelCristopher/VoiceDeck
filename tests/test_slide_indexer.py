import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pymupdf
from voicedeck.indexer.slide_indexer import SlideIndexer


def test_slide_indexer():
    print("[1] Creating synthetic PDF for testing...")
    test_pdf_path = Path(__file__).parent / "test_deck.pdf"

    doc = pymupdf.open()
    # Page 1: Problem & Traction
    page1 = doc.new_page(width=1920, height=1080)
    page1.insert_text((150, 200), "VoiceDeck Pitch Presentation", fontsize=48)
    page1.insert_text((150, 400), "Our quarterly revenue reached 2.5 million dollars.", fontsize=32)

    # Page 2: Growth & Retention
    page2 = doc.new_page(width=1920, height=1080)
    page2.insert_text((150, 200), "Market Traction and Retention", fontsize=48)
    page2.insert_text((150, 450), "Customer retention increased by 85 percent.", fontsize=32)

    doc.save(str(test_pdf_path))
    doc.close()

    print("[2] Loading PDF into SlideIndexer...")
    indexer = SlideIndexer()
    assert indexer.load_pdf(test_pdf_path)
    assert indexer.page_count == 2
    assert indexer.current_page_idx == 0

    print("[3] Searching for 'revenue' on Slide 1...")
    boxes = indexer.find_phrase_boxes("revenue")
    assert len(boxes) == 1
    x0, y0, x1, y1 = boxes[0]
    print(f" -> Found 'revenue' box: ({x0:.3f}, {y0:.3f}, {x1:.3f}, {y1:.3f})")
    assert 0.0 <= x0 < x1 <= 1.0
    assert 0.0 <= y0 < y1 <= 1.0

    print("[4] Searching for multi-word phrase 'million dollars'...")
    multi_boxes = indexer.find_phrase_boxes("million dollars")
    assert len(multi_boxes) == 1
    print(f" -> Found multi-word phrase box: {multi_boxes[0]}")

    print("[5] Moving to Slide 2...")
    indexer.next_page()
    assert indexer.current_page_idx == 1

    boxes_p2 = indexer.find_phrase_boxes("retention")
    assert len(boxes_p2) >= 1
    print(f" -> Found 'retention' on Slide 2 ({len(boxes_p2)} occurrences).")

    # Clean up test pdf
    test_pdf_path.unlink()
    print("\nAll Slide Indexer tests passed successfully!")


if __name__ == "__main__":
    test_slide_indexer()
