#!/usr/bin/env python3
"""
GUI tool to generate a solid-color cycling test video.

Inputs:
- Output filename
- Length (minutes + seconds)
- Resolution dropdown (common presets or custom width/height)

Requires: Python 3, numpy, ffmpeg on PATH.
"""

import colorsys
import math
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Tuple

import numpy as np


PRESETS = {
    "4K UHD (3840x2160)": (3840, 2160),
    "1440p (2560x1440)": (2560, 1440),
    "1080p (1920x1080)": (1920, 1080),
    "720p (1280x720)": (1280, 720),
    "Custom": None,
}


def hsv_to_rgb_uint8(h: float, s: float, v: float) -> Tuple[int, int, int]:
    """Convert HSV (0-1 floats) to 0-255 RGB tuple."""
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def generate_video(
    filename: str,
    total_seconds: float,
    width: int,
    height: int,
    fps: int,
    status_var: tk.StringVar,
    button: ttk.Button,
) -> None:
    total_frames = int(math.ceil(total_seconds * fps))
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

    try:
        for frame_idx in range(total_frames):
            hue = (frame_idx % fps) / fps + frame_idx / total_frames
            hue %= 1.0
            r, g, b = hsv_to_rgb_uint8(hue, 1.0, 1.0)
            frame = np.full((height, width, 3), (r, g, b), dtype=np.uint8)
            proc.stdin.write(frame.tobytes())
    except Exception as exc:  # noqa: BLE001
        status_var.set(f"Error: {exc}")
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()

    if proc.returncode == 0:
        minutes = total_seconds / 60
        status_var.set(f"Done: {minutes:.2f} min -> {filename}")
    else:
        status_var.set(f"ffmpeg exited with {proc.returncode}")
    button.state(["!disabled"])


def start_generation(
    filename_var: tk.StringVar,
    minutes_var: tk.StringVar,
    seconds_var: tk.StringVar,
    width_var: tk.StringVar,
    height_var: tk.StringVar,
    preset_var: tk.StringVar,
    status_var: tk.StringVar,
    button: ttk.Button,
) -> None:
    try:
        minutes = float(minutes_var.get() or 0)
        seconds = float(seconds_var.get() or 0)
    except ValueError:
        status_var.set("Length must be numbers.")
        return

    total_seconds = minutes * 60 + seconds
    if total_seconds <= 0:
        status_var.set("Length must be greater than zero.")
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
    else:
        dims = PRESETS.get(preset)
        if not dims:
            status_var.set("Select a resolution.")
            return
        width, height = dims

    filename = filename_var.get().strip() or "color_cycle.mp4"
    fps = 30

    status_var.set("Rendering… this may take a while.")
    button.state(["disabled"])

    thread = threading.Thread(
        target=generate_video,
        args=(filename, total_seconds, width, height, fps, status_var, button),
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
    root.title("Color Cycle Video Generator")

    filename_var = tk.StringVar(value="color_cycle_4k.mp4")
    minutes_var = tk.StringVar(value="1")
    seconds_var = tk.StringVar(value="0")
    preset_var = tk.StringVar(value="4K UHD (3840x2160)")
    width_var = tk.StringVar(value="1920")
    height_var = tk.StringVar(value="1080")
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

    button = ttk.Button(
        main,
        text="Generate",
        command=lambda: start_generation(
            filename_var,
            minutes_var,
            seconds_var,
            width_var,
            height_var,
            preset_var,
            status_var,
            button,
        ),
    )
    button.grid(row=4, column=0, columnspan=2, pady=(12, 4))

    ttk.Label(main, textvariable=status_var, foreground="blue").grid(
        row=5, column=0, columnspan=2, sticky="w"
    )

    preset_var.trace_add("write", lambda *_: toggle_custom_fields(preset_var=preset_var, custom_frame=custom_frame))

    for i in range(2):
        main.columnconfigure(i, weight=1)

    root.mainloop()


if __name__ == "__main__":
    build_ui()
