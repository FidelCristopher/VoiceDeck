import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication
from voicedeck.overlay.canvas import HighlightOverlay
from voicedeck.ui.app import VoiceDeckMainWindow, WorkerSignals
import yaml

app = QApplication(sys.argv)
signals = WorkerSignals()
config = {
    "app": {"name": "VoiceDeck", "version": "1.0.0"},
    "audio": {},
    "control": {},
    "overlay": {}
}

main_win = VoiceDeckMainWindow(config, signals)
overlay = HighlightOverlay()
print("HighlightOverlay and VoiceDeckMainWindow initialized successfully without errors!")
app.quit()
