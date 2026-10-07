# 🎬 Media Tool – YouTube Downloader & Video Converter

> A desktop GUI application to download YouTube videos/playlists and convert or compress local video files — powered by yt-dlp and FFmpeg.

---

## 📌 About the Project

Media Tool is a Python desktop application with a clean tabbed interface that combines three utilities in one:

- **YouTube Downloader** — download videos, playlists, or audio (MP3) at your chosen quality
- **Video Converter** — convert local video files to MP4, MKV, WEBM, AVI, MP3, M4A, WAV, FLAC
- **Video Compressor** — reduce file size with control over codec, quality level, and resolution

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎥 YouTube Download | Paste one or multiple links; supports playlists |
| 🎵 Audio Extraction | Download as MP3 directly from YouTube |
| 📺 Quality Selection | Choose from 360p to 2160p (4K) |
| 📦 H.264 Preference | Option to prefer H.264 for TV compatibility |
| 🔄 Video Convert | 10 output formats including MP4, MKV, WEBM, MP3, FLAC |
| 🗜️ Video Compress | Light / Medium / Strong compression with resolution scaling |
| ⚡ Smart Re-encode | Skips re-encoding if file is already H.264 (saves time) |
| 📊 Progress Bar | Live progress tracking with stop button |
| 🧵 Threaded | UI stays responsive during long operations |

---

## 🛠️ Tech Stack

- **Language:** Python 3.x
- **GUI:** Tkinter (built-in)
- **Download Engine:** yt-dlp
- **Media Processing:** FFmpeg + FFprobe
- **Threading:** Python `threading` module

---

## 📁 Project Structure

```
Media-Tool/
│
├── media_tool.py        # Main application
├── requirements.txt     # Python dependencies
├── SETUP.md             # Setup and installation guide
└── README.md            # This file
```

> **Note:** `yt-dlp.exe` and `ffmpeg.exe` / `ffprobe.exe` should be placed in the same folder as `media_tool.py` (see SETUP.md).

---

## ⚙️ Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/utkarsh-buildspark/Media-Tool.git
cd Media-Tool

# 2. Install Python dependency
pip install -r requirements.txt

# 3. Add yt-dlp and ffmpeg (see SETUP.md for details)

# 4. Run the app
python media_tool.py
```

---

## 🖥️ Screenshots

> _Add screenshots here after first run_

---

## 🔄 How It Works

```
User pastes YouTube URL / chooses local video
             ↓
  ┌──────────────────────────────────────┐
  │  YouTube Download Tab                │
  │  yt-dlp fetches video + audio        │
  │  FFmpeg merges into MP4              │
  └──────────────────────────────────────┘
             OR
  ┌──────────────────────────────────────┐
  │  Convert / Compress Tab              │
  │  FFprobe reads video metadata        │
  │  FFmpeg re-encodes to target format  │
  │  Smart copy skips re-encode if H.264 │
  └──────────────────────────────────────┘
             ↓
  Progress bar updates live via queue
  Output saved next to original file
```

---

## 📦 Supported Output Formats

| Format | Type |
|---|---|
| MP4 (H.264) | Video |
| MP4 (H.265 / HEVC) | Video |
| MKV (H.264, with subtitles) | Video |
| MKV (H.265, with subtitles) | Video |
| WEBM (VP9) | Video |
| AVI (MPEG-4) | Video |
| MP3 | Audio only |
| M4A (AAC) | Audio only |
| WAV | Audio only |
| FLAC | Audio only |

---

## 👨‍💻 Author

**Utkarsh**

🔗 [LinkedIn](https://www.linkedin.com/in/utkarsh-buildspark)
🌐 [Portfolio](https://build-spark.netlify.app)

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).
