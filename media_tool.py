#!/usr/bin/env python3
"""
Media Tool
  * YouTube Download  : video / playlist / audio (MP3) using yt-dlp
  * Video Convert     : any video -> MP4 / MKV / WEBM / AVI / MP3 / ... using ffmpeg
  * Video Compress    : reduce file size using ffmpeg

yt-dlp and ffmpeg/ffprobe are searched first in the same folder as this script,
then in the current folder, then in the system PATH.
"""
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
EXE = ".exe" if os.name == "nt" else ""
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
VIDEO_TYPES = [
    ("Video / audio files", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v *.ts *.mpg *.mpeg *.3gp *.mp3 *.m4a *.wav *.flac"),
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


# ----------------------------------------------------------------- presets
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-profile:v", "high"]
X265 = ["-c:v", "libx265", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "-tag:v", "hvc1"]
AAC = ["-c:a", "aac", "-b:a", "192k"]
MAP_AV = ["-map", "0:v:0", "-map", "0:a?"]

# name -> (extension, ffmpeg args)
CONVERT = {
    "MP4  (H.264)":            ("mp4",  MAP_AV + X264 + AAC + ["-movflags", "+faststart"]),
    "MP4  (H.265 / HEVC)":     ("mp4",  MAP_AV + X265 + AAC + ["-movflags", "+faststart"]),
    "MKV  (H.264, keeps subtitles)": ("mkv", MAP_AV + ["-map", "0:s?"] + X264 + AAC + ["-c:s", "copy"]),
    "MKV  (H.265, keeps subtitles)": ("mkv", MAP_AV + ["-map", "0:s?"] + X265 + AAC + ["-c:s", "copy"]),
    "WEBM (VP9)":              ("webm", MAP_AV + ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0",
                                                  "-c:a", "libopus", "-b:a", "128k"]),
    "AVI  (MPEG-4)":           ("avi",  MAP_AV + ["-c:v", "mpeg4", "-q:v", "4",
                                                  "-c:a", "libmp3lame", "-q:a", "4"]),
    "MP3  (audio only)":       ("mp3",  ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]),
    "M4A  (audio only, AAC)":  ("m4a",  ["-vn", "-c:a", "aac", "-b:a", "192k"]),
    "WAV  (audio only)":       ("wav",  ["-vn", "-c:a", "pcm_s16le"]),
    "FLAC (audio only)":       ("flac", ["-vn", "-c:a", "flac"]),
}
FIRST_PRESET = "MP4  (H.264)"  # gets the quick "no re-encode" shortcut when possible

COMPRESS_LEVELS = ["Light  (best quality)", "Medium (balanced)", "Strong (smallest size)"]
COMPRESS_CODECS = ["H.264 (plays everywhere)", "H.265 (smaller, device must support it)"]
COMPRESS_RES = ["Keep original", "1080p", "720p", "480p"]
CRF_H264 = [22, 26, 30]
CRF_H265 = [25, 29, 33]

QUALITIES = ["Best available", "2160p", "1440p", "1080p", "720p", "480p", "360p"]


# --------------------------------------------------------------------- app
class App:
    def __init__(self, root):
        self.root = root
        root.title("Media Tool")
        root.geometry("760x720")
        root.minsize(680, 640)

        self.q = queue.Queue()
        self.busy = False
        self.stop_flag = False
        self.proc = None

        self.build_ui()
        self.root.after(100, self.pump)

    # ------------------------------------------------------------------ UI
    def build_ui(self):
        main = ttk.Notebook(self.root)
        main.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.tab_dl = ttk.Frame(main, padding=10)
        self.tab_conv = ttk.Frame(main, padding=6)
        main.add(self.tab_dl, text="  YouTube Download  ")
        main.add(self.tab_conv, text="  Video Convert  ")

        self.build_download_tab()

        inner = ttk.Notebook(self.tab_conv)
        inner.pack(fill="both", expand=True)
        self.tab_convert = ttk.Frame(inner, padding=10)
        self.tab_compress = ttk.Frame(inner, padding=10)
        inner.add(self.tab_convert, text="  Video Convert  ")
        inner.add(self.tab_compress, text="  Video Compress  ")
        self.build_convert_tab()
        self.build_compress_tab()

        # bottom: progress + log
        bottom = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        bottom.pack(fill="both")
        row = ttk.Frame(bottom)
        row.pack(fill="x")
        self.bar = ttk.Progressbar(row, maximum=100)
        self.bar.pack(side="left", fill="x", expand=True)
        self.stop_btn = ttk.Button(row, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))
        self.status = tk.StringVar(value="Ready")
        ttk.Label(bottom, textvariable=self.status).pack(anchor="w", pady=(4, 2))
        self.log = tk.Text(bottom, height=9, wrap="word", state="disabled")
        self.log.pack(fill="both")

    def build_file_list(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        box = tk.Listbox(frame, selectmode="extended", height=7)
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
        t = self.tab_dl
        ttk.Label(t, text="Paste YouTube links (video or playlist), one per line:").pack(anchor="w")
        self.url_text = tk.Text(t, height=6, wrap="none")
        self.url_text.pack(fill="x", pady=4)

        row = ttk.Frame(t)
        row.pack(fill="x")
        ttk.Button(row, text="Load links.txt", command=self.load_links).pack(side="left")
        ttk.Button(row, text="Clear", command=lambda: self.url_text.delete("1.0", "end")).pack(side="left", padx=6)

        opts = ttk.LabelFrame(t, text="Options", padding=8)
        opts.pack(fill="x", pady=10)

        self.dl_mode = tk.StringVar(value="video")
        r1 = ttk.Frame(opts)
        r1.pack(fill="x")
        ttk.Radiobutton(r1, text="Video", variable=self.dl_mode, value="video").pack(side="left")
        ttk.Radiobutton(r1, text="Audio only (MP3)", variable=self.dl_mode, value="audio").pack(side="left", padx=12)

        r2 = ttk.Frame(opts)
        r2.pack(fill="x", pady=6)
        ttk.Label(r2, text="Quality:").pack(side="left")
        self.dl_quality = ttk.Combobox(r2, values=QUALITIES, state="readonly", width=16)
        self.dl_quality.current(3)
        self.dl_quality.pack(side="left", padx=6)

        self.dl_h264 = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts, variable=self.dl_h264,
            text="Prefer H.264 (plays on TV without converting; falls back if not available)",
        ).pack(anchor="w")

        r3 = ttk.Frame(t)
        r3.pack(fill="x")
        ttk.Label(r3, text="Save to:").pack(side="left")
        self.dl_folder = tk.StringVar(value=os.path.join(APP_DIR, "downloads"))
        ttk.Entry(r3, textvariable=self.dl_folder).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(r3, text="Browse...", command=self.pick_folder).pack(side="left")

        ttk.Button(t, text="Download", command=self.start_download).pack(pady=14, ipadx=20, ipady=4)

    def build_convert_tab(self):
        t = self.tab_convert
        ttk.Label(t, text="Choose the video file(s) to convert:").pack(anchor="w")
        self.conv_files = self.build_file_list(t)

        row = ttk.Frame(t)
        row.pack(fill="x", pady=6)
        ttk.Label(row, text="Convert to:").pack(side="left")
        self.conv_fmt = ttk.Combobox(row, values=list(CONVERT), state="readonly", width=32)
        self.conv_fmt.current(0)
        self.conv_fmt.pack(side="left", padx=6)

        ttk.Label(t, text="The converted file is saved in the same folder as the original.",
                  foreground="gray").pack(anchor="w")
        ttk.Button(t, text="Convert", command=self.start_convert).pack(pady=10, ipadx=20, ipady=4)

    def build_compress_tab(self):
        t = self.tab_compress
        ttk.Label(t, text="Choose the video file(s) to compress:").pack(anchor="w")
        self.comp_files = self.build_file_list(t)

        grid = ttk.Frame(t)
        grid.pack(fill="x", pady=6)
        ttk.Label(grid, text="Compression:").grid(row=0, column=0, sticky="w", pady=2)
        self.comp_level = ttk.Combobox(grid, values=COMPRESS_LEVELS, state="readonly", width=34)
        self.comp_level.current(1)
        self.comp_level.grid(row=0, column=1, padx=6)

        ttk.Label(grid, text="Codec:").grid(row=1, column=0, sticky="w", pady=2)
        self.comp_codec = ttk.Combobox(grid, values=COMPRESS_CODECS, state="readonly", width=34)
        self.comp_codec.current(0)
        self.comp_codec.grid(row=1, column=1, padx=6)

        ttk.Label(grid, text="Resolution:").grid(row=2, column=0, sticky="w", pady=2)
        self.comp_res = ttk.Combobox(grid, values=COMPRESS_RES, state="readonly", width=34)
        self.comp_res.current(0)
        self.comp_res.grid(row=2, column=1, padx=6)

        ttk.Label(t, text='Output is saved next to the original as "name_compressed.mp4".',
                  foreground="gray").pack(anchor="w")
        ttk.Button(t, text="Compress", command=self.start_compress).pack(pady=10, ipadx=20, ipady=4)

    # ------------------------------------------------------- small actions
    def pick_folder(self):
        folder = filedialog.askdirectory(title="Choose download folder")
        if folder:
            self.dl_folder.set(folder)

    def load_links(self):
        default = os.path.join(APP_DIR, "links.txt")
        path = default if os.path.isfile(default) else filedialog.askopenfilename(
            title="Choose links.txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        with open(path, encoding="utf-8", errors="replace") as f:
            links = [ln.strip() for ln in f if ln.strip().startswith("http")]
        self.url_text.insert("end", "\n".join(links) + "\n")
        self.say(f"Loaded {len(links)} link(s) from {path}")

    def say(self, text):
        self.q.put(("log", text))

    def stop(self):
        self.stop_flag = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

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
                elif kind == "prog":
                    self.bar["value"] = val
                elif kind == "done":
                    self.busy = False
                    self.stop_btn.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self.pump)

    def start_job(self, target, *args):
        if self.busy:
            messagebox.showinfo("Busy", "Another job is running. Wait for it or press Stop.")
            return
        self.busy = True
        self.stop_flag = False
        self.bar["value"] = 0
        self.stop_btn.configure(state="normal")
        threading.Thread(target=self.guard, args=(target, args), daemon=True).start()

    def guard(self, target, args):
        try:
            target(*args)
        except Exception as e:  # show errors instead of dying silently
            self.say(f"ERROR: {e}")
            self.q.put(("status", "Failed"))
        finally:
            self.q.put(("done", None))

    def stream(self, cmd, on_line):
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", creationflags=NO_WINDOW, bufsize=1)
        for line in self.proc.stdout:
            on_line(line.rstrip())
        self.proc.wait()
        return self.proc.returncode

    # ------------------------------------------------------------ download
    def start_download(self):
        urls = [u.strip() for u in self.url_text.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning("No link", "Paste at least one YouTube link.")
            return
        ytd = ytdlp_cmd()
        if not ytd:
            messagebox.showerror(
                "yt-dlp not found",
                "Put yt-dlp.exe in the same folder as this script, or run:\n\npip install yt-dlp")
            return
        ffmpeg = find_tool("ffmpeg")
        if not ffmpeg and self.dl_mode.get() == "video":
            messagebox.showwarning(
                "ffmpeg not found",
                "ffmpeg is needed to merge video + audio (1080p and above).\n"
                "Put ffmpeg.exe next to this script or add it to PATH.")
            return
        folder = self.dl_folder.get().strip() or os.path.join(APP_DIR, "downloads")
        os.makedirs(folder, exist_ok=True)
        self.start_job(self.do_download, urls, ytd, ffmpeg, folder,
                       self.dl_mode.get(), self.dl_quality.get(), self.dl_h264.get())

    def do_download(self, urls, ytd, ffmpeg, folder, mode, quality, prefer_h264):
        cmd = ytd + ["--newline", "--ignore-errors", "--no-warnings",
                     "-P", folder, "-o", "%(playlist_title&{}/|)s%(title)s.%(ext)s"]
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

        cmd += urls
        pct = re.compile(r"\[download\]\s+([\d.]+)%")

        def on_line(line):
            m = pct.search(line)
            if m:
                self.q.put(("prog", float(m.group(1))))
                self.q.put(("status", line.replace("[download]", "").strip()))
            elif line.strip():
                self.say(line)

        self.q.put(("status", "Starting download..."))
        code = self.stream(cmd, on_line)
        if self.stop_flag:
            self.q.put(("status", "Stopped"))
        elif code == 0:
            self.q.put(("prog", 100))
            self.q.put(("status", f"Done. Saved in {folder}"))
        else:
            self.q.put(("status", "Finished with errors (see log)"))

    # ------------------------------------------------------ convert/compress
    def start_convert(self):
        files = list(self.conv_files.get(0, "end"))
        if not files:
            messagebox.showwarning("No file", "Choose at least one file first.")
            return
        if not find_tool("ffmpeg"):
            messagebox.showerror("ffmpeg not found",
                                 "Put ffmpeg.exe (and ffprobe.exe) next to this script or add them to PATH.")
            return
        name = self.conv_fmt.get()
        ext, args = CONVERT[name]
        jobs = []
        for src in files:
            base = os.path.splitext(src)[0] + "_converted"
            jobs.append((src, unique_path(base, ext), args, name == FIRST_PRESET))
        self.start_job(self.run_jobs, jobs)

    def start_compress(self):
        files = list(self.comp_files.get(0, "end"))
        if not files:
            messagebox.showwarning("No file", "Choose at least one file first.")
            return
        if not find_tool("ffmpeg"):
            messagebox.showerror("ffmpeg not found",
                                 "Put ffmpeg.exe (and ffprobe.exe) next to this script or add them to PATH.")
            return
        level = self.comp_level.current()
        h265 = self.comp_codec.current() == 1
        crf = (CRF_H265 if h265 else CRF_H264)[level]
        args = MAP_AV + ["-c:v", "libx265" if h265 else "libx264", "-preset", "medium",
                         "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if h265:
            args += ["-tag:v", "hvc1"]
        res = self.comp_res.get()
        if res != "Keep original":
            h = res.rstrip("p")
            args += ["-vf", f"scale=-2:min({h}\\,ih)"]  # never upscale
        args += ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]
        jobs = [(src, unique_path(os.path.splitext(src)[0] + "_compressed", "mp4"), args, False)
                for src in files]
        self.start_job(self.run_jobs, jobs)

    def run_jobs(self, jobs):
        ffmpeg = find_tool("ffmpeg")
        total = len(jobs)
        ok = 0
        for i, (src, out, args, allow_copy) in enumerate(jobs):
            if self.stop_flag:
                break
            info = probe(src)
            use_args = args
            if allow_copy and info["vcodec"] == "h264" and info["pix_fmt"] == "yuv420p":
                use_args = MAP_AV + ["-c:v", "copy"] + AAC + ["-movflags", "+faststart"]
                self.say("Video is already H.264 8-bit, so only repacking (fast).")
            name = os.path.basename(src)
            self.q.put(("status", f"[{i + 1}/{total}] {name}"))
            self.say(f"-> {os.path.basename(out)}")

            cmd = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-n", "-i", src] + use_args + \
                  ["-progress", "pipe:1", "-nostats", out]
            dur = info["duration"]

            def on_line(line, i=i):
                m = re.match(r"out_time_(?:ms|us)=(\d+)", line)
                if m and dur:
                    frac = min(int(m.group(1)) / 1e6 / dur, 1.0)
                    self.q.put(("prog", (i + frac) / total * 100))
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
                self.say(f"Done: {out}")
            else:
                self.say(f"FAILED: {name}")
        self.q.put(("prog", 100 if ok == total else self.bar["value"]))
        self.q.put(("status", "Stopped" if self.stop_flag else f"Finished: {ok}/{total} file(s) done"))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
