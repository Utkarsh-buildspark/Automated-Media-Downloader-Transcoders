# Media Tool

A single-file Python GUI that replaces a manual command-line workflow for downloading media and converting or compressing video. Run one script and get a window. If you prefer raw output, switch to CMD Mode and it opens a real console instead.

Built with Python (tkinter), [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ffmpeg](https://ffmpeg.org/). No third-party Python packages required.

---

## Features

| Area | What it does |
|------|--------------|
| **Download → YouTube** | Videos and playlists, quality selection (up to 2160p), H.264 preference, audio-only MP3 |
| **Download → Other sites** | Any site yt-dlp supports (Instagram, Facebook, X, Reddit, and more). Best quality is chosen automatically. Media type: Video, Audio, Image/thumbnail, GIF, or Everything |
| **Convert → Video Convert** | MP4 (H.264 / H.265), MKV, WEBM, AVI, MP3, M4A, WAV, FLAC |
| **Convert → Video Compress** | CRF level, codec, resolution and encoding-speed options |
| **UI Mode / CMD Mode** | UI Mode shows progress inside the window. CMD Mode opens a real console window with the raw tool output |
| **Update Tools** | One click: updates yt-dlp in a console window |

---

## Requirements

| Tool | Purpose | Where to get |
|------|---------|--------------|
| Python 3.8+ | Runs the script (tkinter included) | [python.org](https://www.python.org/downloads/) |
| yt-dlp | Downloads | [releases](https://github.com/yt-dlp/yt-dlp/releases) or `pip install yt-dlp` |
| ffmpeg + ffprobe | Merge, convert, compress | [ffmpeg.org](https://ffmpeg.org/download.html) or `winget install Gyan.FFmpeg` |

Place `yt-dlp.exe`, `ffmpeg.exe` and `ffprobe.exe` next to `media_tool.py`, or have them on `PATH`. Lookup order: script folder, then current folder, then `PATH`.

Run the app:

```
python media_tool.py
```

---

## Interface modes

Chosen with the **Interface** switch at the top of the window.

- **UI Mode**: the tool runs yt-dlp and ffmpeg in the background and shows `X MB of Y MB (Z%) | Speed | ETA` plus a log. Includes a Stop button.
- **CMD Mode**: the same command is launched in a real console window (`cmd.exe /k`, so the window stays open after it finishes). All raw output of yt-dlp and ffmpeg is visible. Close the window to cancel.

> **ETA** means *Estimated Time of Arrival*, the estimated time remaining.

---

## Download → YouTube

Paste links (one per line), pick Video or Audio, quality, and a save folder. An optional custom output filename can be set.

Command used (1080p, H.264 preferred):

```
yt-dlp --newline --ignore-errors --no-warnings \
  -P "downloads" \
  -o "%(playlist_title&{}/|)s%(title)s.%(ext)s" \
  --ffmpeg-location "<ffmpeg folder>" \
  -f "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]" \
  --merge-output-format mp4 \
  <URL>
```

Audio only:

```
yt-dlp ... -f bestaudio/best -x --audio-format mp3 --audio-quality 0 <URL>
```

(`--newline` is only added in UI Mode so progress can be parsed.)

**Format string explained.** YouTube serves 1080p and above as separate video and audio streams. yt-dlp downloads both and ffmpeg merges them.

- `bv*[height<=1080][vcodec^=avc1]` selects the best video up to 1080p whose codec is H.264
- `+ba[ext=m4a]` adds the best AAC audio
- `/bv*[height<=1080]+ba` is the fallback: any codec
- `/b[height<=1080]` is the last fallback: a single pre-merged stream

**Why prefer H.264?** Many TVs and older devices cannot play VP9 or AV1. H.264 plays directly.

Playlists are saved in a sub-folder named after the playlist.

---

## Download → Other sites

Paste links from any site yt-dlp supports. Quality is chosen automatically (best available). Output name: `Title [id].ext`, unless a custom filename is given.

| Media type | yt-dlp arguments |
|------------|------------------|
| Video (best quality) | `-f bv*+ba/b --merge-output-format mp4` |
| Audio only (MP3) | `-f bestaudio/best -x --audio-format mp3 --audio-quality 0` |
| Image / thumbnail | `--skip-download --write-thumbnail --convert-thumbnails jpg` |
| GIF | `-f b[ext=gif]/bv*+ba/b --merge-output-format mp4` (falls back to video if the site has no GIF) |
| Everything | `--write-thumbnail --merge-output-format mp4` |

Notes: availability depends on the site. Some sites offer no choice of quality, and not every site exposes images or GIFs through yt-dlp.

---

## Convert

### Video Convert

Files are saved next to the original with a `_converted` suffix. The original is never touched.

| Option | Codec | Use case |
|--------|-------|----------|
| MP4 (H.264) | libx264 + AAC | Plays everywhere |
| MP4 (H.265 / HEVC) | libx265 + AAC | Smaller files, device must support HEVC |
| MKV (H.264 / H.265) | subtitles copied | Keeps subtitle tracks |
| WEBM (VP9) | libvpx-vp9 + Opus | Web |
| AVI (MPEG-4) | mpeg4 + MP3 | Legacy devices |
| MP3 / M4A / WAV / FLAC | audio only | Extract audio |

Example (MP4 H.264):

```
ffmpeg -hide_banner -loglevel warning -n -i "in.mkv" \
  -map 0:v:0 -map 0:a? \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -profile:v high \
  -c:a aac -b:a 192k -movflags +faststart \
  -progress pipe:1 -nostats "in_converted.mp4"
```

(`-progress pipe:1 -nostats` is UI Mode only. CMD Mode uses ffmpeg's normal console progress.)

**Smart repack.** Before encoding, `ffprobe` checks the source. If it is already H.264 8-bit (`yuv420p`), converting to "MP4 (H.264)" just repacks the streams (`-c:v copy`). This takes seconds instead of minutes, with no quality loss.

### Video Compress

Output: `name_compressed.mp4`.

| Level | H.264 CRF | H.265 CRF |
|-------|-----------|-----------|
| Light (best quality) | 22 | 25 |
| Medium (balanced) | 26 | 29 |
| Strong (smallest size) | 30 | 33 |

Lower CRF means better quality and a bigger file. Resolution can be limited to 1080p, 720p or 480p using `scale=-2:min(H,ih)`, which never upscales. Encoding speed maps to the ffmpeg `-preset` (`ultrafast`, `fast`, `medium`, `slow`).

---

## Update Tools

Opens a console window and runs:

```
yt-dlp -U
```

- If yt-dlp was installed with pip, `python -m pip install -U yt-dlp` is used instead.
- ffmpeg has no built-in updater. To update it, download a fresh build and replace the files next to the script, or run `winget upgrade --id Gyan.FFmpeg -e` if it was installed with winget.

---

## Design notes

- **Threading:** downloads and conversions run in a worker thread. A `queue.Queue` carries log, status and info messages to the UI thread (polled every 100 ms), so the window never freezes.
- **No console flash on Windows:** UI Mode uses `CREATE_NO_WINDOW`. CMD Mode uses `CREATE_NEW_CONSOLE`.
- **CMD quoting:** every argument is double-quoted so characters like `&`, `|`, `<`, `>`, `^` in format strings and templates stay literal.
- **File safety:** outputs are never overwritten (`_1`, `_2`, and so on are appended). Stop or close deletes an incomplete ffmpeg output.
- **Close protection:** closing the window during a job asks for confirmation and terminates the child process.

---

## File structure

```
media_tool/
├── media_tool.py     # the whole app
├── yt-dlp.exe        # optional: or on PATH / pip
├── ffmpeg.exe        # optional: or on PATH
├── ffprobe.exe       # optional: or on PATH
├── downloads/        # default download folder (auto-created)
├── .gitignore
└── README.md
```

Only the Python standard library is used (`tkinter`, `subprocess`, `threading`, `queue`, `re`, `json`, `os`, `shutil`, `shlex`).

---

## Author

**Utkarsh**

🔗 [LinkedIn](https://www.linkedin.com/in/utkarsh-buildspark)
🌐 [Portfolio](https://build-spark.netlify.app)
