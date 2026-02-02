#!/usr/bin/env python3
"""
Batch runner with overlays and live progress.

- Select multiple input videos (default from ./media), choose overlays (timestamp, frame counter, watermark).
- Runs ffmpeg sequentially; shows per-job progress, ETA, and live fps estimate.
- Outputs to media/<name>_proc.mp4 (or user choice).
"""

import math
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk, messagebox


def ffprobe_info(path: str):
    """Return (duration_sec, fps_guess) using ffprobe."""
    try:
        # duration
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path],
            text=True,
        )
        duration = float(out.strip())
    except Exception:
        duration = 0.0
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=r_frame_rate",
                "-of",
                "default=nk=1:nw=1",
                path,
            ],
            text=True,
        )
        num, den = out.strip().split("/")
        fps = float(num) / float(den)
    except Exception:
        fps = 30.0
    return duration, fps


def build_overlay_filter(use_timestamp: bool, use_frame: bool, watermark: str):
    filters = []
    if use_timestamp:
        filters.append(
            "drawtext=fontfile=/Library/Fonts/Arial.ttf:text='%{pts\\:hms}':x=10:y=10:fontsize=32:fontcolor=white@0.9:box=1:boxcolor=0x00000055"
        )
    if use_frame:
        filters.append(
            "drawtext=fontfile=/Library/Fonts/Arial.ttf:text='frame %{frame_num}':x=10:y=50:fontsize=28:fontcolor=yellow@0.9:box=1:boxcolor=0x00000055"
        )
    if watermark:
        filters.append(
            f"drawtext=fontfile=/Library/Fonts/Arial.ttf:text='{watermark}':x=w-tw-20:y=h-th-20:fontsize=32:fontcolor=white@0.85:box=1:boxcolor=0x00000055"
        )
    return ",".join(filters) if filters else None


class JobRunner(threading.Thread):
    def __init__(self, jobs, progress_queue):
        super().__init__(daemon=True)
        self.jobs = jobs
        self.q = progress_queue

    def run(self):
        for path, out_path, filt in self.jobs:
            duration, fps_guess = ffprobe_info(path)
            total_frames_est = int(duration * fps_guess) if duration > 0 else None
            cmd = ["ffmpeg", "-y", "-i", path]
            if filt:
                cmd += ["-vf", filt]
            cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "slow", "-c:a", "copy", "-progress", "pipe:1", "-nostats", out_path]
            start = time.time()
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, universal_newlines=True)
            last_frame = 0
            while True:
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    continue
                if line.startswith("frame="):
                    try:
                        last_frame = int(line.split("=")[1].strip())
                    except Exception:
                        pass
                if line.startswith("out_time_ms=") and total_frames_est:
                    try:
                        out_ms = int(line.split("=")[1].strip())
                        cur_time = out_ms / 1000000.0
                        done_ratio = min(1.0, cur_time / duration) if duration else 0
                        elapsed = time.time() - start
                        fps_now = last_frame / elapsed if elapsed > 0 else 0
                        eta = (elapsed / done_ratio - elapsed) if done_ratio > 0 else 0
                        self.q.put(("progress", path, done_ratio, fps_now, eta))
                    except Exception:
                        pass
            proc.wait()
            elapsed = time.time() - start
            self.q.put(("done", path, proc.returncode, elapsed))
        self.q.put(("all_done",))


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Batch Runner")
        self.jobs = []
        self.q = queue.Queue()
        self.build_ui()

    def add_files(self):
        paths = filedialog.askopenfilenames(initialdir="media", filetypes=[("Videos", "*.mp4 *.mov *.mkv *.webm")])
        for p in paths:
            out_name = os.path.splitext(os.path.basename(p))[0] + "_proc.mp4"
            out_path = os.path.join("media", out_name)
            self.listbox.insert(tk.END, f"{p} -> {out_path}")
            self.jobs.append((p, out_path, None))

    def start(self):
        if not self.jobs:
            messagebox.showerror("No jobs", "Add at least one video.")
            return
        use_ts = self.timestamp_var.get()
        use_frame = self.frame_var.get()
        wm = self.watermark_var.get().strip()
        filt = build_overlay_filter(use_ts, use_frame, wm)
        # apply same filter to all jobs
        jobs = [(p, outp, filt) for (p, outp, _) in self.jobs]
        self.progress["value"] = 0
        self.status.set("Running...")
        runner = JobRunner(jobs, self.q)
        runner.start()
        self.root.after(200, self.poll_queue)

    def poll_queue(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "progress":
                    _, path, ratio, fps_now, eta = item
                    self.progress["value"] = ratio * 100
                    self.fps_var.set(f"FPS: {fps_now:0.1f}")
                    self.eta_var.set(f"ETA: {eta:0.1f}s")
                    self.status.set(f"Processing: {os.path.basename(path)}")
                elif item[0] == "done":
                    _, path, code, elapsed = item
                    self.status.set(f"Finished {os.path.basename(path)} (code {code}) in {elapsed:0.1f}s")
                elif item[0] == "all_done":
                    self.status.set("All jobs done.")
                    return
        except queue.Empty:
            pass
        self.root.after(200, self.poll_queue)

    def build_ui(self):
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        ttk.Button(frm, text="Add videos", command=self.add_files).grid(row=0, column=0, sticky="w")
        ttk.Button(frm, text="Start", command=self.start).grid(row=0, column=1, sticky="e")

        self.listbox = tk.Listbox(frm, width=70, height=8)
        self.listbox.grid(row=1, column=0, columnspan=2, pady=6, sticky="nsew")

        self.timestamp_var = tk.BooleanVar(value=True)
        self.frame_var = tk.BooleanVar(value=True)
        self.watermark_var = tk.StringVar(value="MediaLab")

        ttk.Checkbutton(frm, text="Timestamp", variable=self.timestamp_var).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(frm, text="Frame counter", variable=self.frame_var).grid(row=2, column=1, sticky="w")
        ttk.Label(frm, text="Watermark").grid(row=3, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.watermark_var, width=24).grid(row=3, column=1, sticky="w")

        self.progress = ttk.Progressbar(frm, maximum=100)
        self.progress.grid(row=4, column=0, columnspan=2, sticky="ew", pady=6)
        self.status = tk.StringVar(value="Idle")
        self.fps_var = tk.StringVar(value="FPS: -")
        self.eta_var = tk.StringVar(value="ETA: -")
        ttk.Label(frm, textvariable=self.status).grid(row=5, column=0, columnspan=2, sticky="w")
        ttk.Label(frm, textvariable=self.fps_var).grid(row=6, column=0, sticky="w")
        ttk.Label(frm, textvariable=self.eta_var).grid(row=6, column=1, sticky="e")

        for i in range(2):
            frm.columnconfigure(i, weight=1)


def main():
    if "--cli" in sys.argv:
        print("GUI only; use the window to run batch jobs.")
        return
    App().root.mainloop()


if __name__ == "__main__":
    main()
