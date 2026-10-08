import os
import zipfile
import requests
from pathlib import Path
from tqdm import tqdm

MODEL_URLS = {
    "en": {
        "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        "folder_name": "vosk-model-small-en-us-0.15",
    },
}

def ensure_model(language: str = "en", models_dir: Path | str = "models") -> Path:
    """
    Checks if the Vosk model exists; if not, downloads and extracts it.
    Returns the Path to the model directory.
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    if language not in MODEL_URLS:
        raise ValueError(f"Unsupported language '{language}'. Supported: {list(MODEL_URLS.keys())}")

    target_info = MODEL_URLS[language]
    expected_path = models_dir / target_info["folder_name"]

    if expected_path.exists() and expected_path.is_dir():
        return expected_path

    zip_path = models_dir / f"{target_info['folder_name']}.zip"
    url = target_info["url"]

    print(f"[VoiceDeck] Model '{language}' not found. Downloading from {url}...")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    with open(zip_path, "wb") as f, tqdm(
        desc=f"Downloading {language} model",
        total=total_size,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=1024 * 64):
            size = f.write(data)
            bar.update(size)

    print(f"[VoiceDeck] Extracting {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(models_dir)

    # Clean up zip archive
    if zip_path.exists():
        zip_path.unlink()

    print(f"[VoiceDeck] Model ready at: {expected_path}")
    return expected_path

if __name__ == "__main__":
    ensure_model("en")
