#!/usr/bin/env python3
"""
GUI tool to generate gradient-based color-cycling test videos.

Behavior:
- Uses multiple moving sine-wave gradients with random colors/directions.
- Waves overlap additively each frame (uint8 wrap for bright, fast motion).

Inputs via a Tkinter UI: filename, length (minutes/seconds), resolution dropdown
(with custom), and FPS.

Requires: Python 3, numpy, ffmpeg on PATH.
"""

import colorsys
import math
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import List

import numpy as np


PRESETS = {
    "4K UHD (3840x2160)": (3840, 2160),
    "1440p (2560x1440)": (2560, 1440),
    "1080p (1920x1080)": (1920, 1080),
    "720p (1280x720)": (1280, 720),
    "Custom": None,
}


class Wave:
    __slots__ = ("dot_term", "temp_freq", "phase", "hue0", "hue_speed", "amp_scale")


def generate_video(
    filename: str,
    total_seconds: float,
    width: int,
    height: int,
    fps: int,
    status_var: tk.StringVar,
    button: ttk.Button,
) -> None:
    if "." not in filename:
        filename += ".mp4"

    dup_factor = 5  # duplicate each generated frame this many times
    target_frames = int(math.ceil(total_seconds * fps))

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        filename,
    ]

    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    except FileNotFoundError:
        status_var.set("ffmpeg not found on PATH.")
        button.state(["!disabled"])
        return

    rng = np.random.default_rng()
    # Coordinate grids
    x = np.linspace(-0.5, 0.5, width, dtype=np.float32)
    y = np.linspace(-0.5, 0.5, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    waves: List[Wave] = []
    num_waves = 3
    for _ in range(num_waves):
        angle = rng.uniform(0.0, 2 * math.pi)
        dx, dy = math.cos(angle), math.sin(angle)
        spatial_cycles = rng.uniform(1.0, 6.0)  # cycles across the frame
        temp_freq = rng.uniform(0.8, 4.0)  # Hz
        phase = rng.uniform(0.0, 2 * math.pi)
        hue0 = rng.random()
        hue_speed = rng.uniform(0.05, 0.35)  # hue cycles per second
        amp_scale = rng.uniform(0.5, 1.0)

        dot = (xx * dx + yy * dy) * spatial_cycles
        w = Wave()
        w.dot_term = dot  # float32 (H, W)
        w.temp_freq = temp_freq
        w.phase = phase
        w.hue0 = hue0
        w.hue_speed = hue_speed
        w.amp_scale = amp_scale
        waves.append(w)

    try:
        frames_written = 0
        logical_index = 0
        while frames_written < target_frames:
            t = frames_written / fps  # time corresponding to first duplicate
            accum = np.zeros((height, width, 3), dtype=np.float32)
            for w in waves:
                arg = 2 * math.pi * (w.dot_term + t * w.temp_freq) + w.phase
                s = (np.sin(arg, dtype=np.float32) + 1.0) * 0.5  # 0..1
                hue = (w.hue0 + t * w.hue_speed) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                rgb = np.array([r, g, b], dtype=np.float32) * 255.0 * w.amp_scale
                s = s[..., None] * rgb
                accum += s
            frame = (accum.astype(np.uint16) & 0xFF).astype(np.uint8)
            repeat = min(dup_factor, target_frames - frames_written)
            for _ in range(repeat):
                proc.stdin.write(frame.tobytes())
            frames_written += repeat
            logical_index += 1
    except Exception as exc:  # noqa: BLE001
        status_var.set(f"Error: {exc}")
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()

    if proc.returncode == 0:
        status_var.set(f"Done: {total_seconds:.1f}s -> {filename}")
    else:
        status_var.set(f"ffmpeg exited with {proc.returncode}")
    button.state(["!disabled"])


def start_generation(
    filename_var: tk.StringVar,
    minutes_var: tk.StringVar,
    seconds_var: tk.StringVar,
    width_var: tk.StringVar,
    height_var: tk.StringVar,
    fps_var: tk.StringVar,
    preset_var: tk.StringVar,
    status_var: tk.StringVar,
    button: ttk.Button,
) -> None:
    try:
        minutes = float(minutes_var.get() or 0)
        seconds = float(seconds_var.get() or 0)
        fps = float(fps_var.get() or 0)
    except ValueError:
        status_var.set("Length/FPS must be numbers.")
        return

    total_seconds = minutes * 60 + seconds
    if total_seconds <= 0:
        status_var.set("Length must be greater than zero.")
        return
    if fps <= 0:
        status_var.set("FPS must be positive.")
        return

    preset = preset_var.get()
    if preset == "Custom":
        try:
            width = int(width_var.get())
            height = int(height_var.get())
        except ValueError:
            status_var.set("Custom width/height must be integers.")
            return
        if width <= 0 or height <= 0:
            status_var.set("Custom width/height must be positive.")
            return
        if width > 3840 or height > 2160:
            status_var.set("Max resolution is 3840x2160.")
            return
    else:
        dims = PRESETS.get(preset)
        if not dims:
            status_var.set("Select a resolution.")
            return
        width, height = dims

    filename = filename_var.get().strip() or "media/gradient_cycle.mp4"

    status_var.set("Rendering… this may take a while.")
    button.state(["disabled"])

    thread = threading.Thread(
        target=generate_video,
        args=(filename, total_seconds, width, height, int(fps), status_var, button),
        daemon=True,
    )
    thread.start()


def toggle_custom_fields(*_, preset_var: tk.StringVar, custom_frame: ttk.Frame) -> None:
    if preset_var.get() == "Custom":
        custom_frame.state(["!disabled"])
    else:
        custom_frame.state(["disabled"])


def build_ui() -> None:
    root = tk.Tk()
    root.title("Gradient Cycle Video Generator")

    filename_var = tk.StringVar(value="media/gradient_cycle.mp4")
    minutes_var = tk.StringVar(value="1")
    seconds_var = tk.StringVar(value="0")
    preset_var = tk.StringVar(value="1080p (1920x1080)")
    width_var = tk.StringVar(value="1920")
    height_var = tk.StringVar(value="1080")
    fps_var = tk.StringVar(value="30")
    status_var = tk.StringVar(value="Idle")

    main = ttk.Frame(root, padding=16)
    main.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    ttk.Label(main, text="Output filename").grid(row=0, column=0, sticky="w")
    ttk.Entry(main, textvariable=filename_var, width=32).grid(row=0, column=1, sticky="ew")

    ttk.Label(main, text="Length (min/sec)").grid(row=1, column=0, sticky="w")
    len_frame = ttk.Frame(main)
    len_frame.grid(row=1, column=1, sticky="w")
    ttk.Entry(len_frame, width=6, textvariable=minutes_var).grid(row=0, column=0)
    ttk.Label(len_frame, text="min").grid(row=0, column=1, padx=4)
    ttk.Entry(len_frame, width=6, textvariable=seconds_var).grid(row=0, column=2)
    ttk.Label(len_frame, text="sec").grid(row=0, column=3, padx=4)

    ttk.Label(main, text="Resolution").grid(row=2, column=0, sticky="w")
    preset_menu = ttk.OptionMenu(main, preset_var, preset_var.get(), *PRESETS.keys())
    preset_menu.grid(row=2, column=1, sticky="w")

    custom_frame = ttk.Frame(main)
    custom_frame.grid(row=3, column=1, sticky="w", pady=(4, 0))
    ttk.Label(custom_frame, text="W").grid(row=0, column=0)
    ttk.Entry(custom_frame, width=6, textvariable=width_var).grid(row=0, column=1, padx=4)
    ttk.Label(custom_frame, text="H").grid(row=0, column=2)
    ttk.Entry(custom_frame, width=6, textvariable=height_var).grid(row=0, column=3, padx=4)
    custom_frame.state(["disabled"])

    ttk.Label(main, text="FPS").grid(row=4, column=0, sticky="w")
    ttk.Entry(main, width=6, textvariable=fps_var).grid(row=4, column=1, sticky="w")

    button = ttk.Button(
        main,
        text="Generate",
        command=lambda: start_generation(
            filename_var,
            minutes_var,
            seconds_var,
            width_var,
            height_var,
            fps_var,
            preset_var,
            status_var,
            button,
        ),
    )
    button.grid(row=5, column=0, columnspan=2, pady=(12, 4))

    ttk.Label(main, textvariable=status_var, foreground="blue").grid(
        row=6, column=0, columnspan=2, sticky="w"
    )

    preset_var.trace_add("write", lambda *_: toggle_custom_fields(preset_var=preset_var, custom_frame=custom_frame))

    for i in range(2):
        main.columnconfigure(i, weight=1)

    root.mainloop()


if __name__ == "__main__":
    build_ui()
