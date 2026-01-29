#!/usr/bin/env python3
"""
GUI tool to generate gradient-based color-cycling test videos.

Behavior:
- Every ~2.5s a random 0-255 RGB target and random gradient direction are chosen.
- Gradients blend between targets; frames add together with uint8 wraparound
  (overflow is intentional to create bright flashes).

Inputs via a Tkinter UI: filename, length (minutes/seconds), resolution dropdown
(with custom), and FPS.

Requires: Python 3, numpy, ffmpeg on PATH.
"""

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


def random_color(rng: np.random.Generator) -> np.ndarray:
    # uint16 to allow accumulation before wrap
    return rng.integers(0, 256, size=3, dtype=np.uint16)


def random_cardinal_dir(rng: np.random.Generator) -> float:
    """Return a direction in radians: up, down, left, or right."""
    return rng.choice([0.0, math.pi / 2, math.pi, 3 * math.pi / 2])


def make_gradient_map(width: int, height: int, direction: float, color: np.ndarray) -> np.ndarray:
    """
    Create a color gradient for a given direction (radians) and target color.
    Gradient goes from black to color along the direction; values in float32.
    """
    # Centered coordinates preserve direction (0 vs 180 are distinct).
    x = np.linspace(-0.5, 0.5, width, dtype=np.float32)
    y = np.linspace(-0.5, 0.5, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    dx = math.cos(direction)
    dy = math.sin(direction)
    proj = xx * dx + yy * dy  # range roughly [-sqrt(0.5), +sqrt(0.5)]
    max_r = math.sqrt(0.5)
    proj = (proj + max_r) / (2 * max_r + 1e-6)  # normalize to 0..1 while keeping direction
    proj = np.clip(proj, 0.0, 1.0)
    grad = proj[..., None] * color.astype(np.float32)
    return grad  # float32 (H, W, 3)


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

    total_frames = int(math.ceil(total_seconds * fps))
    segment_seconds = 4.0  # slower changes to observe direction clearly
    segment_frames = max(1, int(segment_seconds * fps))

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
    accumulator = np.zeros((height, width, 3), dtype=np.uint16)

    current_color = random_color(rng)
    next_color = random_color(rng)
    current_dir = random_cardinal_dir(rng)
    current_grad = make_gradient_map(width, height, current_dir, current_color)
    try:
        for frame_idx in range(total_frames):
            seg_pos = frame_idx % segment_frames
            if seg_pos == 0 and frame_idx != 0:
                current_color = next_color
                next_color = random_color(rng)
                current_dir = random_cardinal_dir(rng)
                current_grad = make_gradient_map(width, height, current_dir, current_color)
                # additive between segments, but constant during segment
                accumulator = accumulator + current_grad.astype(np.uint16)
            elif frame_idx == 0:
                # first segment: add once
                accumulator = accumulator + current_grad.astype(np.uint16)

            frame = (accumulator & 0xFF).astype(np.uint8)
            proc.stdin.write(frame.tobytes())
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

    filename = filename_var.get().strip() or "gradient_cycle.mp4"

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

    filename_var = tk.StringVar(value="gradient_cycle.mp4")
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
