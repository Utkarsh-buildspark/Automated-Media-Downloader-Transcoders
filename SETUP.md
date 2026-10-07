# ⚙️ Media Tool – Setup Guide

---

## ✅ Requirements

- Windows 10 / 11
- Python 3.8 or above → [Download here](https://www.python.org/downloads/)
- yt-dlp
- FFmpeg + FFprobe

---

## 📦 Step 1 — Install Python Dependency

```bash
pip install yt-dlp
```

---

## 📥 Step 2 — Download FFmpeg

1. Go to [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Download the Windows build (recommended: **gyan.dev** full build)
3. Extract the zip
4. Copy `ffmpeg.exe` and `ffprobe.exe` from the `bin` folder
5. Paste them into the **same folder as `media_tool.py`**

---

## 📥 Step 3 — Download yt-dlp (optional — already installed via pip)

If you want a standalone `.exe` instead:

1. Go to [https://github.com/yt-dlp/yt-dlp/releases](https://github.com/yt-dlp/yt-dlp/releases)
2. Download `yt-dlp.exe`
3. Place it in the **same folder as `media_tool.py`**

---

## 📁 Final Folder Structure

```
Media-Tool/
├── media_tool.py
├── ffmpeg.exe
├── ffprobe.exe
├── yt-dlp.exe       (optional if installed via pip)
└── downloads/       (auto-created on first download)
```

---

## ▶️ Step 4 — Run the App

```bash
python media_tool.py
```

The GUI window will open with three tabs: YouTube Download, Video Convert, and Video Compress.

---

## 🎯 How to Use

### YouTube Download
1. Paste one or more YouTube links (one per line)
2. Select Video or Audio only (MP3)
3. Choose quality (default: 1080p)
4. Enable "Prefer H.264" for TV playback compatibility
5. Set download folder
6. Click **Download**

### Video Convert
1. Click **Choose files** and select your video(s)
2. Pick output format from the dropdown (e.g. MP4 H.264, MKV, MP3)
3. Click **Convert**
4. Output is saved next to the original file

### Video Compress
1. Click **Choose files** and select your video(s)
2. Choose compression level, codec, and resolution
3. Click **Compress**
4. Output is saved as `filename_compressed.mp4`

---

## ❌ Common Errors & Fixes

| Error | Fix |
|---|---|
| `ffmpeg not found` | Place `ffmpeg.exe` and `ffprobe.exe` in the same folder as the script |
| `yt-dlp not found` | Run `pip install yt-dlp` or place `yt-dlp.exe` in the folder |
| Download fails at 1080p | Enable "Prefer H.264" option or lower quality |
| `No module named tkinter` | Reinstall Python and check "tcl/tk" option during setup |
