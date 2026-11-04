# Media Tool - Setup Guide

Step-by-step instructions to run Media Tool on Windows.

---

## Requirements

- Windows 10 / 11
- Python 3.8 or above ([download](https://www.python.org/downloads/)). During installation, tick "Add Python to PATH". Keep the "tcl/tk" option enabled so tkinter is available.
- yt-dlp
- ffmpeg and ffprobe

---

## Step 1: Download the project

```bash
git clone https://github.com/utkarsh-buildspark/Media-Tool.git
cd Media-Tool
```

Or download the ZIP from GitHub and extract it.

---

## Step 2: Install yt-dlp

Either install with pip:

```bash
pip install yt-dlp
```

Or download `yt-dlp.exe` from [github.com/yt-dlp/yt-dlp/releases](https://github.com/yt-dlp/yt-dlp/releases) and place it in the same folder as `media_tool.py`.

---

## Step 3: Install ffmpeg and ffprobe

Option A, with winget:

```bash
winget install Gyan.FFmpeg
```

Option B, manually:

1. Download a Windows build from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extract the archive
3. Copy `ffmpeg.exe` and `ffprobe.exe` from the `bin` folder
4. Paste them next to `media_tool.py`

The app looks for tools in this order: script folder, current folder, system PATH.

---

## Step 4: Run the app

```bash
python media_tool.py
```

---

## How to use

### Download: YouTube
1. Paste one or more links, one per line
2. Choose Video or Audio only (MP3)
3. Choose a quality (default 1080p)
4. Optionally set an output filename and a save folder
5. Click Download

### Download: Other sites
1. Paste links from any site yt-dlp supports
2. Choose a media type: Video, Audio, Image/thumbnail, GIF, or Everything
3. Click Download

### Convert: Video Convert
1. Click Choose files and select one or more videos
2. Pick an output format and encoding speed
3. Click Convert. The result is saved next to the original with a `_converted` suffix.

### Convert: Video Compress
1. Select files
2. Choose compression level, codec, resolution and encoding speed
3. Click Compress. The result is saved as `name_compressed.mp4`.

### Interface modes
- UI Mode shows progress, speed and ETA inside the window
- CMD Mode opens a real console window with the raw tool output

### Update Tools
Click Update Tools to update yt-dlp in a console window.

---

## Common errors and fixes

| Error | Fix |
|---|---|
| yt-dlp not found | Run `pip install yt-dlp` or place `yt-dlp.exe` next to the script |
| ffmpeg not found | Place `ffmpeg.exe` and `ffprobe.exe` next to the script, or add them to PATH |
| `No module named tkinter` | Reinstall Python and keep the tcl/tk option enabled |
| 1080p download fails | Lower the quality, or run Update Tools to get the latest yt-dlp |
