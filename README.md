# VoiceDeck 🎤⚡
> **Hands-Free Pitching Assistant:** Kontrol slide presentasi dan sorot kata-kata kunci di layar hanya dengan suara Anda secara 100% offline.

---

## 🏗️ Speech & System Architecture

VoiceDeck dirancang dengan arsitektur audio streaming berlatensi rendah:

```
[ Microphone (16kHz PCM Stream) ]
                │
                ▼
      [ AudioCapture & Ring Buffer ]
                │
                ├───> [ Energy VAD / Noise Adaptation ]
                │
                ▼
     [ Vosk ASR Engine (Offline / Local) ]
                │
                ├───> Partial Result Stream (<100ms) ──> [ Fast KWS Triggers ]
                └───> Final Transcript Stream        ──> [ Intent Parser ]
                                                              │
                     ┌────────────────────────────────────────┴────────────────────────────────────────┐
                     ▼                                                                                 ▼
          [ SlideController ]                                                             [ HighlightOverlay ]
     (Simulates Key.right / Key.left)                                                  (Transparent Click-Through Canvas)
     PowerPoint / PDF / Canva slides                                                   Visual highlight banner & feedback
```

### Keunggulan Utama untuk Panggung Pitching:
1. **100% On-Device / Offline:** Tidak membutuhkan koneksi internet. Aman dari gangguan Wi-Fi di venue lomba.
2. **Dual-Speed Response:** Menggunakan *Partial Result Stream* untuk deteksi kata `"next"` / `"back"` secepat menekan clicker fisik (<100 ms).
3. **Transparent Click-Through Overlay:** Window transparan selalu di atas (always-on-top) tanpa mengganggu klik mouse atau fokus software presentasi Anda.
4. **Smart Debounce:** Mencegah perpindahan slide ganda saat presenter berbicara cepat.

---

## 🚀 Cara Menjalankan

### Opsi 1: Menggunakan Script Windows (Paling Mudah)
Cukup buka folder `C:\Users\Pongo\VoiceDeck` di File Explorer, lalu **double-click** file:
```
run.bat
```

### Opsi 2: Menggunakan Terminal (PowerShell / Command Prompt)
```powershell
cd C:\Users\Pongo\VoiceDeck
.\.venv\Scripts\python.exe main.py
```
*(Saat pertama kali dijalankan, VoiceDeck akan otomatis mengunduh model kecil Vosk ~39MB ke folder `models/`)*

---

## 🗣️ Perintah Suara Bawaan (Default Voice Commands)

| Aksi | Perintah Bahasa Inggris | Perintah Bahasa Indonesia |
| :--- | :--- | :--- |
| **Maju Slide** | `"next"`, `"next slide"` | `"lanjut"`, `"berikutnya"`, `"maju"` |
| **Mundur Slide** | `"back"`, `"previous"` | `"kembali"`, `"mundur"`, `"sebelumnya"` |
| **Highlight Kata** | `"highlight <kata>"` | `"sorot <kata>"`, `"tandai <kata>"` |

> *Contoh:*
> - Bicara: *"Next slide"* ➔ Slide berpindah ke kanan.
> - Bicara: *"Highlight revenue"* ➔ Layar menampilkan animasi sorot kuning menyala: **✨ REVENUE**.

---

## ⚙️ Konfigurasi (`config.yaml`)

Anda dapat menyesuaikan kata kunci, sensitivitas audio, dan warna sorotan di `config.yaml`:

```yaml
app:
  language: "en" # 'en' (Inggris) atau 'id' (Indonesia)

control:
  debounce_seconds: 1.2 # Jeda minimum antar perpindahan slide
  keywords:
    next:
      - "next"
      - "lanjut"
      - "berikutnya"
    highlight:
      - "highlight"
      - "sorot"
      - "tandai"

overlay:
  auto_fade_seconds: 3.5 # Durasi highlight bertahan di layar
```

---

## 📂 Struktur Project

```
VoiceDeck/
├── config.yaml                     # Konfigurasi trigger & timing
├── requirements.txt                # Dependensi Python
├── run.bat                         # Launcher Windows
├── main.py                         # Application Entry Point
├── voicedeck/
│   ├── audio/
│   │   ├── capture.py              # Thread-safe mic capture & volume metering
│   │   └── vad.py                  # Voice Activity Detection (Energy & Adaptive Floor)
│   ├── engine/
│   │   └── speech_engine.py        # Vosk local speech recognition engine
│   ├── controller/
│   │   ├── slide_controller.py     # Keyboard dispatcher (Right/Left) + debounce
│   │   └── intent_parser.py        # Intent & keyword entity extraction
│   ├── overlay/
│   │   └── canvas.py               # Transparent always-on-top HUD & highlighter
│   ├── ui/
│   │   └── app.py                  # PyQt6 Control Dashboard
│   └── downloader.py               # Automatic model manager
└── models/                         # Penyimpanan model ASR offline
```
