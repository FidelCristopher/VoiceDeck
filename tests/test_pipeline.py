import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voicedeck.controller.intent_parser import IntentParser
from voicedeck.audio.vad import EnergyVAD
from voicedeck.downloader import ensure_model
from voicedeck.engine.speech_engine import SpeechEngine

def test_pipeline():
    print("[1] Testing Intent Parser...")
    keywords = {
        "next": ["next", "next slide", "lanjut"],
        "previous": ["back", "previous", "kembali"],
        "highlight": ["highlight", "sorot"],
    }
    parser = IntentParser(keywords)

    assert parser.parse("can we go to the next slide please") == ("NEXT", None)
    assert parser.parse("please go back") == ("PREVIOUS", None)
    assert parser.parse("highlight key traction metric") == ("HIGHLIGHT", "key traction metric")
    assert parser.parse("clear highlight") == ("CLEAR", None)
    print(" -> Intent Parser passed!")

    print("[2] Testing VAD...")
    vad = EnergyVAD()
    silent_bytes = b"\x00\x00" * 4000
    assert not vad.is_speech(silent_bytes)
    print(" -> VAD passed!")

    print("[3] Testing Vosk Model Loader...")
    model_path = ensure_model("en", models_dir="models")
    engine = SpeechEngine(model_path)
    assert engine.recognizer is not None
    print(" -> Model loaded successfully!")

    print("\nAll pipeline components verified successfully! Ready to run on Windows.")

if __name__ == "__main__":
    test_pipeline()
