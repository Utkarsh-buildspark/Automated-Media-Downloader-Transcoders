#!/usr/bin/env python3
"""
Media Tool
  * Download : YouTube (video / playlist / audio) and any other site supported by yt-dlp
  * Convert  : convert local video files to other formats, or compress them (ffmpeg)
  * Interface: UI Mode (progress shown in this window) or CMD Mode (real console window)
  * Update   : one-click update of yt-dlp and ffmpeg

yt-dlp and ffmpeg/ffprobe are searched first in the same folder as this script,
then in the current folder, then in the system PATH.
"""
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
IS_WIN = os.name == "nt"
EXE = ".exe" if IS_WIN else ""
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
VIDEO_TYPES = [
    ("Video / audio files",
     "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v *.ts *.mpg *.mpeg *.3gp *.mp3 *.m4a *.wav *.flac"),
    ("All files", "*.*"),
]


# ----------------------------------------------------------------- helpers
def find_tool(name):
    for folder in (APP_DIR, os.getcwd()):
        path = os.path.join(folder, name + EXE)
        if os.path.isfile(path):
            return path
    return shutil.which(name)


def ytdlp_cmd():
    path = find_tool("yt-dlp")
    if path:
        return [path]
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return None


def probe(path):
    """Return duration (seconds), video codec and pixel format of a file."""
    info = {"duration": 0.0, "vcodec": None, "pix_fmt": None}
    ffprobe = find_tool("ffprobe")
    if not ffprobe:
        return info
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=NO_WINDOW,
        ).stdout
        data = json.loads(out)
        info["duration"] = float(data.get("format", {}).get("duration") or 0)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                info["vcodec"] = stream.get("codec_name")
                info["pix_fmt"] = stream.get("pix_fmt")
                break
    except Exception:
        pass
    return info


def unique_path(base, ext):
    path = f"{base}.{ext}"
    n = 1
    while os.path.exists(path):
        path = f"{base}_{n}.{ext}"
        n += 1
    return path


def fmt_bytes(b):
    """Human-readable file size string."""
    try:
        b = float(b)
    except (TypeError, ValueError):
        return "? MB"
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def fmt_eta(secs):
    """Human-readable ETA (Estimated Time of Arrival = time remaining)."""
    try:
        secs = int(float(secs))
    except (TypeError, ValueError):
        return "?:??"
    if secs < 0:
        return "?:??"
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def cmd_quote(arg):
    """Quote one argument for cmd.exe (always, so & | < > ^ stay literal)."""
    return '"' + str(arg).replace('"', '\\"') + '"'


def run_in_console(cmds):
    """Open a real console window and run the given commands one after another.
    The window stays open afterwards so the output can be read. Returns True on success."""
    try:
        if IS_WIN:
            line = " & ".join(" ".join(cmd_quote(a) for a in c) for c in cmds)
            subprocess.Popen(f'cmd.exe /k "{line}"', creationflags=NEW_CONSOLE)
            return True
        script = " ; ".join(shlex.join(c) for c in cmds) + " ; echo ; read -r -p 'Press Enter to close...'"
        for term, prefix in (("x-terminal-emulator", ["-e"]), ("gnome-terminal", ["--"]),
                             ("konsole", ["-e"]), ("xterm", ["-e"])):
            if shutil.which(term):
                subprocess.Popen([term] + prefix + ["bash", "-c", script])
                return True
    except Exception:
        pass
    return False


# ----------------------------------------------------------------- presets
def make_x264(preset="medium"):
    return ["-c:v", "libx264", "-preset", preset, "-crf", "20",
            "-pix_fmt", "yuv420p", "-profile:v", "high"]


def make_x265(preset="medium"):
    return ["-c:v", "libx265", "-preset", preset, "-crf", "23",
            "-pix_fmt", "yuv420p", "-tag:v", "hvc1"]


AAC_HQ = ["-c:a", "aac", "-b:a", "192k"]
AAC_LQ = ["-c:a", "aac", "-b:a", "128k"]
MAP_AV = ["-map", "0:v:0", "-map", "0:a?"]

# name -> (extension, callable(preset) -> args)
CONVERT = {
    "MP4  (H.264)":                  ("mp4",  lambda p: MAP_AV + make_x264(p) + AAC_HQ + ["-movflags", "+faststart"]),
    "MP4  (H.265 / HEVC)":           ("mp4",  lambda p: MAP_AV + make_x265(p) + AAC_HQ + ["-movflags", "+faststart"]),
    "MKV  (H.264, keeps subtitles)": ("mkv",  lambda p: MAP_AV + ["-map", "0:s?"] + make_x264(p) + AAC_HQ + ["-c:s", "copy"]),
    "MKV  (H.265, keeps subtitles)": ("mkv",  lambda p: MAP_AV + ["-map", "0:s?"] + make_x265(p) + AAC_HQ + ["-c:s", "copy"]),
    "WEBM (VP9)":                    ("webm", lambda p: MAP_AV + ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0",
                                                                   "-c:a", "libopus", "-b:a", "128k"]),
    "AVI  (MPEG-4)":                 ("avi",  lambda p: MAP_AV + ["-c:v", "mpeg4", "-q:v", "4",
                                                                   "-c:a", "libmp3lame", "-q:a", "4"]),
    "MP3  (audio only)":             ("mp3",  lambda p: ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]),
    "M4A  (audio only, AAC)":        ("m4a",  lambda p: ["-vn", "-c:a", "aac", "-b:a", "192k"]),
    "WAV  (audio only)":             ("wav",  lambda p: ["-vn", "-c:a", "pcm_s16le"]),
    "FLAC (audio only)":             ("flac", lambda p: ["-vn", "-c:a", "flac"]),
}
FIRST_PRESET = "MP4  (H.264)"

COMPRESS_LEVELS = ["Light  (best quality)", "Medium (balanced)", "Strong (smallest size)"]
COMPRESS_CODECS = ["H.264 (plays everywhere)", "H.265 (smaller, device must support it)"]
COMPRESS_RES = ["Keep original", "1080p", "720p", "480p"]
SPEED_OPTIONS = ["Ultrafast (fastest, bigger file)", "Fast", "Normal (balanced)", "Slow (smallest, best quality)"]
SPEED_PRESETS = ["ultrafast", "fast", "medium", "slow"]
CRF_H264 = [22, 26, 30]
CRF_H265 = [25, 29, 33]

QUALITIES = ["Best available", "2160p", "1440p", "1080p", "720p", "480p", "360p"]

# "Other sites" media types -> yt-dlp arguments
OTHER_MEDIA = [
    ("Video (best quality)",
     ["-f", "bv*+ba/b", "--merge-output-format", "mp4"]),
    ("Audio only (MP3)",
     ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"]),
    ("Image / thumbnail",
     ["--skip-download", "--write-thumbnail", "--convert-thumbnails", "jpg"]),
    ("GIF (falls back to video if no GIF exists)",
     ["-f", "b[ext=gif]/bv*+ba/b", "--merge-output-format", "mp4"]),
    ("Everything (video + thumbnail)",
     ["--write-thumbnail", "--merge-output-format", "mp4"]),
]


def build_youtube_cmd(ytd, ffmpeg, folder, urls, mode, quality, prefer_h264, live, custom_name=""):
    """yt-dlp command for the YouTube tab. live=True adds --newline for UI parsing."""
    if custom_name:
        out_tmpl = f"{custom_name}.%(ext)s"
    else:
        out_tmpl = "%(playlist_title&{}/|)s%(title)s.%(ext)s"
    cmd = list(ytd) + (["--newline"] if live else []) + [
        "--ignore-errors", "--no-warnings", "-P", folder,
        "-o", out_tmpl]
    if ffmpeg:
        cmd += ["--ffmpeg-location", os.path.dirname(ffmpeg) or "."]
    if mode == "audio":
        cmd += ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        m = re.match(r"(\d+)p", quality)
        hf = f"[height<={m.group(1)}]" if m else ""
        if prefer_h264:
            fmt = f"bv*{hf}[vcodec^=avc1]+ba[ext=m4a]/bv*{hf}+ba/b{hf}"
        else:
            fmt = f"bv*{hf}+ba/b{hf}"
        cmd += ["-f", fmt, "--merge-output-format", "mp4"]
    return cmd + list(urls)


def build_other_cmd(ytd, ffmpeg, folder, urls, media_index, live, custom_name=""):
    """yt-dlp command for the Other-sites tab: best quality chosen by yt-dlp itself."""
    if custom_name:
        out_tmpl = f"{custom_name}.%(ext)s"
    else:
        out_tmpl = "%(title).150s [%(id)s].%(ext)s"
    cmd = list(ytd) + (["--newline"] if live else []) + [
        "--ignore-errors", "--no-warnings", "-P", folder,
        "-o", out_tmpl]
    if ffmpeg:
        cmd += ["--ffmpeg-location", os.path.dirname(ffmpeg) or "."]
    cmd += OTHER_MEDIA[media_index][1]
    return cmd + list(urls)


def resolve_ffmpeg_args(args, allow_copy, info):
    """Return (args, repack_only). Repack instead of re-encode if already H.264 8-bit."""
    if allow_copy and info["vcodec"] == "h264" and info["pix_fmt"] == "yuv420p":
        return MAP_AV + ["-c:v", "copy"] + AAC_HQ + ["-movflags", "+faststart"], True
    return args, False


# --------------------------------------------------------------------- app
class App:
    def __init__(self, root):
        self.root = root
        root.title("Automated Media Downloader & Transcoder — Made by Utkarsh")
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w = min(820, int(sw * 0.6))
        h = min(int(sh * 0.88), sh - 60)
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2 - 20)
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(680, min(600, h))
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.q = queue.Queue()
        self.busy = False
        self.stop_flag = False
        self.proc = None
        self.mode = tk.StringVar(value="ui")      # "ui" or "cmd"

        self.build_ui()
        self.root.after(100, self.pump)

    # ------------------------------------------------------ close handler
    def on_close(self):
        if self.busy:
            answer = messagebox.askyesno(
                "Job in progress",
                "A job is currently running.\n\n"
                "Closing now may leave an incomplete output file.\n\n"
                "Close anyway?",
                icon="warning",
            )
            if not answer:
                return
            self.stop_flag = True
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                except Exception:
                    pass
        self.root.destroy()

    # ------------------------------------------------------------------ UI
    def build_ui(self):
        # interface mode selector
        top = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Interface:", font=("", 9, "bold")).pack(side="left")
        ttk.Radiobutton(top, text="UI Mode", variable=self.mode, value="ui").pack(side="left", padx=(8, 0))
        ttk.Radiobutton(top, text="CMD Mode", variable=self.mode, value="cmd").pack(side="left", padx=8)
        ttk.Label(top, text="(CMD Mode opens a real console window with raw tool output)",
                  foreground="gray").pack(side="left")

        main = ttk.Notebook(self.root)
        main.pack(fill="both", expand=True, padx=8, pady=(6, 4))

        self.tab_dl = ttk.Frame(main, padding=6)
        self.tab_conv = ttk.Frame(main, padding=6)
        main.add(self.tab_dl, text="  Download  ")
        main.add(self.tab_conv, text="  Convert  ")

        self.build_download_tab()

        inner = ttk.Notebook(self.tab_conv)
        inner.pack(fill="both", expand=True)
        self.tab_convert = ttk.Frame(inner, padding=10)
        self.tab_compress = ttk.Frame(inner, padding=10)
        inner.add(self.tab_convert, text="  Video Convert  ")
        inner.add(self.tab_compress, text="  Video Compress  ")
        self.build_convert_tab()
        self.build_compress_tab()

        # bottom: info line + stop/update buttons + status + log
        bottom = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        bottom.pack(fill="both", expand=True)

        # info line (speed / ETA / MB) — highlighted, shown above buttons
        self.info_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.info_var,
                  foreground="#cc2200", font=("", 10, "bold")).pack(anchor="w", pady=(2, 0))

        row = ttk.Frame(bottom)
        row.pack(fill="x", pady=(4, 0))

        # Stop button — pure red bg + pure white bold text
        self.stop_btn = tk.Button(
            row, text="Stop", command=self.stop, state="disabled",
            bg="#cc0000", fg="white", activebackground="#990000", activeforeground="white",
            font=("", 10, "bold"), relief="raised", overrelief="sunken", bd=2, padx=14, pady=4,
            disabledforeground="white",
        )
        self.stop_btn.pack(side="left")

        tk.Button(
            row, text="Clear Log", command=self._clear_log,
            bg="#2471a3", fg="white", activebackground="#1a5276", activeforeground="white",
            font=("", 9, "bold"), relief="raised", overrelief="sunken", bd=2, padx=12, pady=3,
        ).pack(side="left", padx=8)

        ttk.Button(row, text="Update Tools", command=self.update_tools).pack(side="right")

        self.status = tk.StringVar(value="Ready")
        status_row = ttk.Frame(bottom)
        status_row.pack(fill="x", pady=(2, 1))
        ttk.Label(status_row, textvariable=self.status, font=("", 9)).pack(side="left")

        self._log_expanded = False
        self._expand_btn = ttk.Button(status_row, text="▼ Expand Log",
                                      command=self._toggle_log)
        self._expand_btn.pack(side="right")

        # log box — collapsed by default (2 lines), expand on demand
        self.log = tk.Text(bottom, height=2, wrap="word", state="disabled",
                           font=("Consolas", 9), relief="solid", bd=2)
        self.log.pack(fill="x", pady=(0, 6))

        footer = ttk.Frame(self.root, padding=(8, 2, 8, 6))
        footer.pack(fill="x")
        ttk.Label(footer, text="Built by Utkarsh  ·  © 2026",
                  font=("", 10, "bold"), foreground="#1a6fcc").pack(side="right")
        ttk.Label(footer, text="Automated Media Downloader & Transcoder — Made by Utkarsh",
                  font=("", 9), foreground="#555").pack(side="left")

    def build_file_list(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        box = tk.Listbox(frame, selectmode="extended", height=6)
        sb = ttk.Scrollbar(frame, command=box.yview)
        box.configure(yscrollcommand=sb.set)
        box.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        btns = ttk.Frame(parent)
        btns.pack(fill="x", pady=4)

        def add():
            for f in filedialog.askopenfilenames(title="Choose video files", filetypes=VIDEO_TYPES):
                if f not in box.get(0, "end"):
                    box.insert("end", f)

        def remove():
            for i in reversed(box.curselection()):
                box.delete(i)

        ttk.Button(btns, text="Choose files...", command=add).pack(side="left")
        ttk.Button(btns, text="Remove selected", command=remove).pack(side="left", padx=6)
        ttk.Button(btns, text="Clear", command=lambda: box.delete(0, "end")).pack(side="left")
        return box

    def build_download_tab(self):
        self.dl_folder = tk.StringVar(value=os.path.join(APP_DIR, "downloads"))
        self.yt_custom_name = tk.StringVar()
        self.other_custom_name = tk.StringVar()

        nb = ttk.Notebook(self.tab_dl)
        nb.pack(fill="both", expand=True)
        yt = ttk.Frame(nb, padding=10)
        other = ttk.Frame(nb, padding=10)
        nb.add(yt, text="  YouTube  ")
        nb.add(other, text="  Other sites  ")

        # ---- YouTube
        ttk.Label(yt, text="Paste YouTube links (video or playlist), one per line:").pack(anchor="w")
        self.url_text = tk.Text(yt, height=6, wrap="none")
        self.url_text.pack(fill="x", pady=4)
        self._add_paste_menu(self.url_text)
        ttk.Button(yt, text="Clear",
                   command=lambda: self.url_text.delete("1.0", "end")).pack(anchor="w")

        opts = ttk.LabelFrame(yt, text="Options", padding=8)
        opts.pack(fill="x", pady=10)

        self.dl_mode = tk.StringVar(value="video")
        r1 = ttk.Frame(opts)
        r1.pack(fill="x")
        ttk.Radiobutton(r1, text="Video", variable=self.dl_mode, value="video").pack(side="left")
        ttk.Radiobutton(r1, text="Audio only (MP3)",
                        variable=self.dl_mode, value="audio").pack(side="left", padx=12)

        r2 = ttk.Frame(opts)
        r2.pack(fill="x", pady=6)
        ttk.Label(r2, text="Quality:").pack(side="left")
        self.dl_quality = ttk.Combobox(r2, values=QUALITIES, state="readonly", width=16)
        self.dl_quality.current(3)
        self.dl_quality.pack(side="left", padx=6)


        nr = ttk.Frame(yt)
        nr.pack(fill="x", pady=(6, 0))
        ttk.Label(nr, text="Output filename (optional):").pack(anchor="w")
        ttk.Entry(nr, textvariable=self.yt_custom_name).pack(fill="x")
        ttk.Label(nr, text="Leave blank to use the video title. Extension is added automatically.",
                  foreground="gray").pack(anchor="w")

        self.build_folder_row(yt)
        ttk.Button(yt, text="Download",
                   command=self.start_youtube).pack(pady=14, ipadx=20, ipady=4)

        # ---- Other sites
        ttk.Label(other, text="Paste links from any other site (Instagram, Facebook, X, Reddit, ...), "
                              "one per line:").pack(anchor="w")
        self.other_text = tk.Text(other, height=6, wrap="none")
        self.other_text.pack(fill="x", pady=4)
        self._add_paste_menu(self.other_text)
        ttk.Button(other, text="Clear",
                   command=lambda: self.other_text.delete("1.0", "end")).pack(anchor="w")

        oopts = ttk.LabelFrame(other, text="Media type", padding=8)
        oopts.pack(fill="x", pady=10)
        self.other_media = ttk.Combobox(oopts, values=[m[0] for m in OTHER_MEDIA],
                                        state="readonly", width=46)
        self.other_media.current(0)
        self.other_media.pack(anchor="w")
        ttk.Label(oopts, text="Quality is chosen automatically (best available).",
                  foreground="gray").pack(anchor="w", pady=(6, 0))

        onr = ttk.Frame(other)
        onr.pack(fill="x", pady=(6, 0))
        ttk.Label(onr, text="Output filename (optional):").pack(anchor="w")
        ttk.Entry(onr, textvariable=self.other_custom_name).pack(fill="x")
        ttk.Label(onr, text="Leave blank to use the video title. Extension is added automatically.",
                  foreground="gray").pack(anchor="w")

        self.build_folder_row(other)
        ttk.Button(other, text="Download",
                   command=self.start_other).pack(pady=14, ipadx=20, ipady=4)

    def build_folder_row(self, parent):
        r = ttk.Frame(parent)
        r.pack(fill="x")
        ttk.Label(r, text="Save to:").pack(side="left")
        ttk.Entry(r, textvariable=self.dl_folder).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r, text="Browse...", command=self.pick_folder).pack(side="left")

    def build_convert_tab(self):
        t = self.tab_convert
        ttk.Label(t, text="Choose the video file(s) to convert:").pack(anchor="w")
        self.conv_files = self.build_file_list(t)

        row = ttk.Frame(t)
        row.pack(fill="x", pady=(6, 2))
        ttk.Label(row, text="Convert to:").pack(side="left")
        self.conv_fmt = ttk.Combobox(row, values=list(CONVERT), state="readonly", width=32)
        self.conv_fmt.current(0)
        self.conv_fmt.pack(side="left", padx=6)

        row2 = ttk.Frame(t)
        row2.pack(fill="x", pady=(0, 4))
        ttk.Label(row2, text="Encoding speed:").pack(side="left")
        self.conv_speed = ttk.Combobox(row2, values=SPEED_OPTIONS, state="readonly", width=34)
        self.conv_speed.current(2)   # Normal
        self.conv_speed.pack(side="left", padx=6)

        ttk.Label(t, text="Converted file is saved in the same folder as the original (with _converted suffix).",
                  foreground="gray").pack(anchor="w")
        ttk.Button(t, text="Convert", command=self.start_convert).pack(pady=10, ipadx=20, ipady=4)

    def build_compress_tab(self):
        t = self.tab_compress
        ttk.Label(t, text="Choose the video file(s) to compress:").pack(anchor="w")
        self.comp_files = self.build_file_list(t)

        grid = ttk.Frame(t)
        grid.pack(fill="x", pady=6)

        ttk.Label(grid, text="Compression:").grid(row=0, column=0, sticky="w", pady=2)
        self.comp_level = ttk.Combobox(grid, values=COMPRESS_LEVELS, state="readonly", width=36)
        self.comp_level.current(1)
        self.comp_level.grid(row=0, column=1, padx=6)

        ttk.Label(grid, text="Codec:").grid(row=1, column=0, sticky="w", pady=2)
        self.comp_codec = ttk.Combobox(grid, values=COMPRESS_CODECS, state="readonly", width=36)
        self.comp_codec.current(0)
        self.comp_codec.grid(row=1, column=1, padx=6)

        ttk.Label(grid, text="Resolution:").grid(row=2, column=0, sticky="w", pady=2)
        self.comp_res = ttk.Combobox(grid, values=COMPRESS_RES, state="readonly", width=36)
        self.comp_res.current(0)
        self.comp_res.grid(row=2, column=1, padx=6)

        ttk.Label(grid, text="Encoding speed:").grid(row=3, column=0, sticky="w", pady=2)
        self.comp_speed = ttk.Combobox(grid, values=SPEED_OPTIONS, state="readonly", width=36)
        self.comp_speed.current(2)   # Normal
        self.comp_speed.grid(row=3, column=1, padx=6)

        ttk.Label(t, text='Output saved next to original as "name_compressed.mp4".',
                  foreground="gray").pack(anchor="w")
        ttk.Button(t, text="Compress", command=self.start_compress).pack(pady=10, ipadx=20, ipady=4)

    # ------------------------------------------------------- small actions
    def pick_folder(self):
        folder = filedialog.askdirectory(title="Choose download folder")
        if folder:
            self.dl_folder.set(folder)

    def say(self, text):
        self.q.put(("log", text))

    def _set_stop_state(self, enabled):
        if enabled:
            self.stop_btn.configure(state="normal", bg="#cc0000", fg="white")
        else:
            self.stop_btn.configure(state="disabled", bg="#cc0000")

    def stop(self):
        self.stop_flag = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _toggle_log(self):
        if self._log_expanded:
            self.log.configure(height=2)
            self.log.pack_configure(fill="x", expand=False)
            self._expand_btn.configure(text="▼ Expand Log")
            self._log_expanded = False
        else:
            self.log.configure(height=12)
            self.log.pack_configure(fill="both", expand=True)
            self._expand_btn.configure(text="▲ Collapse Log")
            self._log_expanded = True

    @staticmethod
    def _add_paste_menu(widget):
        """Right-click context menu with Copy / Paste / Cut / Select All."""
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Cut",        command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy",       command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste",      command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: widget.event_generate("<<SelectAll>>"))

        def show(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", show)

    def open_console(self, cmds, what):
        """CMD Mode: run commands in a real console window."""
        if run_in_console(cmds):
            self.status.set(f"{what} started in a CMD window.")
            self.info_var.set("")
        else:
            messagebox.showerror("Console not available",
                                 "Could not open a console window. Switch to UI Mode instead.")

    def update_tools(self):
        if self.busy:
            messagebox.showinfo("Job already running",
                                "A job is already running. Please wait for it to finish or press Stop.")
            return
        ytd = ytdlp_cmd()
        cmds = []
        lines = []
        if ytd:
            if len(ytd) == 1:
                cmds.append(ytd + ["-U"])
                lines.append("yt-dlp   ->  yt-dlp -U")
            else:
                cmds.append([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])
                lines.append("yt-dlp   ->  pip install -U yt-dlp")
        if not cmds:
            messagebox.showinfo("Nothing to update", "yt-dlp was not found in PATH or next to this script.")
            return
        if not messagebox.askyesno(
                "Update tools",
                "A CMD window will open and run:\n\n  " + "\n  ".join(lines) + "\n\nContinue?"):
            return
        self.open_console(cmds, "Update")

    # ----------------------------------------------------- queue -> widgets
    def pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", val + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "status":
                    self.status.set(val)
                elif kind == "info":
                    self.info_var.set(val)
                elif kind == "done":
                    self.busy = False
                    self._set_stop_state(False)
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def start_job(self, target, *args):
        if self.busy:
            messagebox.showinfo("Job already running",
                                "A job is already running. Please wait for it to finish or press Stop.")
            return
        self.busy = True
        self.stop_flag = False
        self.info_var.set("")
        self._set_stop_state(True)
        threading.Thread(target=self.guard, args=(target, args), daemon=True).start()

    def guard(self, target, args):
        try:
            target(*args)
        except Exception as e:
            self.say(f"ERROR: {e}")
            self.q.put(("status", "Failed"))
        finally:
            self.q.put(("done", None))
            self.q.put(("info", ""))

    def stream(self, cmd, on_line):
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", creationflags=NO_WINDOW, bufsize=1)
        for line in self.proc.stdout:
            if self.stop_flag:
                self.proc.terminate()
                try:
                    self.proc.stdout.read()   # drain so process can exit
                except Exception:
                    pass
                break
            on_line(line.rstrip())
        self.proc.wait()
        return self.proc.returncode

    # ------------------------------------------------------------ download
    @staticmethod
    def read_urls(widget):
        return [u.strip() for u in widget.get("1.0", "end").splitlines() if u.strip()]

    def download_folder(self):
        folder = self.dl_folder.get().strip() or os.path.join(APP_DIR, "downloads")
        os.makedirs(folder, exist_ok=True)
        return folder

    def start_youtube(self):
        urls = self.read_urls(self.url_text)
        if not urls:
            messagebox.showwarning("No link", "Please paste at least one YouTube link.")
            return
        ytd = ytdlp_cmd()
        if not ytd:
            messagebox.showerror(
                "yt-dlp not found",
                "Put yt-dlp.exe in the same folder as this script, or run:\n\npip install yt-dlp")
            return
        ffmpeg = find_tool("ffmpeg")
        if not ffmpeg:
            messagebox.showwarning(
                "ffmpeg not found",
                "ffmpeg is needed to merge video + audio and to create MP3.\n"
                "Put ffmpeg.exe next to this script or add it to PATH.")
            return
        folder = self.download_folder()
        live = self.mode.get() == "ui"
        cname = self.yt_custom_name.get().strip()
        cmd = build_youtube_cmd(ytd, ffmpeg, folder, urls, self.dl_mode.get(),
                                self.dl_quality.get(), True, live, cname)
        if live:
            self.start_job(self.do_download, cmd, folder)
        else:
            self.open_console([cmd], "Download")

    def start_other(self):
        urls = self.read_urls(self.other_text)
        if not urls:
            messagebox.showwarning("No link", "Please paste at least one link.")
            return
        ytd = ytdlp_cmd()
        if not ytd:
            messagebox.showerror(
                "yt-dlp not found",
                "Put yt-dlp.exe in the same folder as this script, or run:\n\npip install yt-dlp")
            return
        ffmpeg = find_tool("ffmpeg")
        folder = self.download_folder()
        live = self.mode.get() == "ui"
        cname = self.other_custom_name.get().strip()
        cmd = build_other_cmd(ytd, ffmpeg, folder, urls, self.other_media.current(), live, cname)
        if live:
            self.start_job(self.do_download, cmd, folder)
        else:
            self.open_console([cmd], "Download")

    def do_download(self, cmd, folder):
        # Example yt-dlp line: [download]  47.3% of   234.50MiB at    2.30MiB/s ETA 01:23
        pct_re = re.compile(
            r"\[download\]\s+([\d.]+)%\s+of\s+~?\s*([\d.]+)\s*(\S+)\s+at\s+([\d.]+\s*\S+/s)\s+ETA\s+(\S+)")
        pct_simple = re.compile(r"\[download\]\s+([\d.]+)%")

        def on_line(line):
            m = pct_re.search(line)
            if m:
                pct_s, total_val, total_unit, speed, eta = m.groups()
                try:
                    downloaded = float(pct_s) / 100.0 * float(total_val)
                    dl_str = f"{downloaded:.2f} {total_unit}"
                except ValueError:
                    dl_str = "..."
                self.q.put(("info",
                            f"📥  {dl_str} of {total_val} {total_unit} ({pct_s}%)"
                            f"  |  Speed: {speed}  |  ETA: {eta}"))
                self.q.put(("status", line.replace("[download]", "").strip()))
            elif pct_simple.search(line):
                self.q.put(("status", line.replace("[download]", "").strip()))
            elif line.strip():
                self.say(line)

        self.q.put(("status", "Starting download..."))
        code = self.stream(cmd, on_line)
        if self.stop_flag:
            self.q.put(("status", "Stopped"))
        elif code == 0:
            self.q.put(("status", f"Done. Saved in: {folder}"))
        else:
            self.q.put(("status", "Finished with errors (see log)"))

    # ------------------------------------------------------ convert/compress
    def start_convert(self):
        files = list(self.conv_files.get(0, "end"))
        if not files:
            messagebox.showwarning("No file selected", "Please select at least one file.")
            return
        if not find_tool("ffmpeg"):
            messagebox.showerror("ffmpeg not found",
                                 "Put ffmpeg.exe (and ffprobe.exe) next to this script or add them to PATH.")
            return
        name = self.conv_fmt.get()
        ext, args_fn = CONVERT[name]
        preset = SPEED_PRESETS[self.conv_speed.current()]
        args = args_fn(preset)
        jobs = []
        for src in files:
            base = os.path.splitext(src)[0] + "_converted"
            jobs.append((src, unique_path(base, ext), args, name == FIRST_PRESET, preset))
        self.dispatch_jobs(jobs)

    def start_compress(self):
        files = list(self.comp_files.get(0, "end"))
        if not files:
            messagebox.showwarning("No file selected", "Please select at least one file.")
            return
        if not find_tool("ffmpeg"):
            messagebox.showerror("ffmpeg not found",
                                 "Put ffmpeg.exe (and ffprobe.exe) next to this script or add them to PATH.")
            return
        level = self.comp_level.current()
        h265 = self.comp_codec.current() == 1
        preset = SPEED_PRESETS[self.comp_speed.current()]
        crf = (CRF_H265 if h265 else CRF_H264)[level]

        args = MAP_AV + ["-c:v", "libx265" if h265 else "libx264",
                         "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if h265:
            args += ["-tag:v", "hvc1"]
        res = self.comp_res.get()
        if res != "Keep original":
            h = res.rstrip("p")
            args += ["-vf", f"scale=-2:min({h}\\,ih)"]
        args += AAC_LQ + ["-movflags", "+faststart"]

        jobs = [(src, unique_path(os.path.splitext(src)[0] + "_compressed", "mp4"), args, False, preset)
                for src in files]
        self.dispatch_jobs(jobs)

    def dispatch_jobs(self, jobs):
        """UI Mode -> run in background thread; CMD Mode -> real console window."""
        if self.mode.get() == "ui":
            self.start_job(self.run_jobs, jobs)
            return
        ffmpeg = find_tool("ffmpeg")
        cmds = []
        for src, out, args, allow_copy, _preset in jobs:
            use_args, _ = resolve_ffmpeg_args(args, allow_copy, probe(src))
            cmds.append([ffmpeg, "-hide_banner", "-n", "-i", src] + use_args + [out])
        self.open_console(cmds, "Conversion")

    def run_jobs(self, jobs):
        ffmpeg = find_tool("ffmpeg")
        total = len(jobs)
        ok = 0

        # ffmpeg -progress pipe:1 emits key=value lines
        time_re = re.compile(r"out_time_(?:ms|us)=(\d+)")
        size_re = re.compile(r"total_size=(\d+)")
        speed_re = re.compile(r"speed=([\d.]+)x")

        for i, (src, out, args, allow_copy, preset) in enumerate(jobs):
            if self.stop_flag:
                break

            info = probe(src)
            use_args, repack = resolve_ffmpeg_args(args, allow_copy, info)
            if repack:
                self.say("Video is already H.264 (8-bit) — repacking only (will finish quickly).")

            fname = os.path.basename(src)
            self.q.put(("status", f"[{i + 1}/{total}]  {fname}  |  preset: {preset}"))
            self.say(f"-> {os.path.basename(out)}")

            try:
                src_size = os.path.getsize(src)
            except OSError:
                src_size = 0

            cmd = ([ffmpeg, "-hide_banner", "-loglevel", "warning", "-n", "-i", src]
                   + use_args
                   + ["-progress", "pipe:1", "-nostats", out])
            dur = info["duration"]

            job_state = {"cur_size": 0, "cur_speed": "", "elapsed_s": 0.0}

            def on_line(line, dur=dur, state=job_state, src_size=src_size):
                tm = time_re.match(line)
                sm = size_re.match(line)
                spm = speed_re.match(line)

                if tm:
                    state["elapsed_s"] = int(tm.group(1)) / 1e6
                elif sm:
                    state["cur_size"] = int(sm.group(1))
                elif spm:
                    state["cur_speed"] = spm.group(1) + "x"
                elif line.strip() in ("progress=continue", "progress=end"):
                    elapsed_s = state["elapsed_s"]
                    written = state["cur_size"]
                    speed_str = state["cur_speed"] or "..."

                    if src_size > 0 and written > 0:
                        pct = min(written / src_size * 100, 100.0)
                        size_info = (f"{fmt_bytes(written)} of {fmt_bytes(src_size)} converted "
                                     f"({pct:.1f}%)")
                    elif written > 0:
                        size_info = f"{fmt_bytes(written)} converted"
                    else:
                        size_info = "Starting..."

                    try:
                        eta_s = (dur - elapsed_s) / float(speed_str.rstrip("x")) if dur else -1
                    except (ValueError, ZeroDivisionError):
                        eta_s = -1

                    self.q.put(("info",
                                f"⚙️  {size_info}  |  Speed: {speed_str}  |  ETA: {fmt_eta(eta_s)}"))
                elif line.strip() and not re.match(r"^\w+=", line):
                    self.say(line)

            code = self.stream(cmd, on_line)

            if self.stop_flag:
                if os.path.exists(out):
                    try:
                        os.remove(out)
                    except OSError:
                        pass
                break
            if code == 0:
                ok += 1
                out_size = fmt_bytes(os.path.getsize(out)) if os.path.exists(out) else "?"
                self.say(f"Done: {os.path.basename(out)}  ({out_size})")
            else:
                self.say(f"FAILED: {fname}")

        self.q.put(("status",
                    "Stopped" if self.stop_flag else f"Finished: {ok}/{total} file(s) done"))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
