#!/usr/bin/env python3
"""
Abstract flow generator: layered evolving waves and noise for a painterly look.

Features:
- Three layered flow fields with different scales/speeds.
- HSV-based coloring with random palette drift.
- Optional frame duplication to reduce CPU cost.
- GUI with Tkinter; CLI fallback via --cli.
"""

import math
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np


def hsv_to_rgb(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    i = np.floor(h * 6).astype(np.int32)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r = np.choose(i % 6, [v, q, p, p, t, v])
    g = np.choose(i % 6, [t, v, v, q, p, p])
    b = np.choose(i % 6, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


def run(filename: str, minutes: float, seconds: float, width: int, height: int, fps: int, dup: int) -> None:
    if "." not in filename:
        filename += ".mp4"
    if not filename.startswith("media/"):
        filename = f"media/{filename}"
    if width > 3840 or height > 2160:
        raise ValueError("Max resolution is 3840x2160.")
    total_seconds = minutes * 60 + seconds
    if total_seconds <= 0:
        raise ValueError("Length must be greater than zero.")
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
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    rng = np.random.default_rng()
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    # Layer params
    layers = []
    for scale, speed in [(1.4, 0.35), (2.3, 0.6), (3.7, 0.9)]:
        angle = rng.uniform(0, 2 * math.pi)
        dx, dy = math.cos(angle), math.sin(angle)
        layer = {
            "dx": dx,
            "dy": dy,
            "scale": scale,
            "speed": speed,
            "hue0": rng.random(),
            "hue_rate": rng.uniform(0.05, 0.25),
        }
        layers.append(layer)

    try:
        frames_written = 0
        logical_idx = 0
        while frames_written < target_frames:
            t = logical_idx / fps
            accum = np.zeros((height, width, 3), dtype=np.float32)
            for layer in layers:
                phase = (xx * layer["dx"] + yy * layer["dy"]) * layer["scale"]
                arg = 2 * math.pi * (phase + t * layer["speed"])
                wave = (np.sin(arg, dtype=np.float32) + 1.0) * 0.5
                hue = (layer["hue0"] + layer["hue_rate"] * t + 0.15 * wave) % 1.0
                sat = np.clip(0.6 + 0.4 * wave, 0.0, 1.0)
                val = np.clip(0.35 + 0.65 * wave, 0.0, 1.0)
                rgb = hsv_to_rgb(hue, sat, val)
                accum += rgb * 255.0
            frame = np.clip(accum / len(layers), 0, 255).astype(np.uint8)
            repeat = min(dup, target_frames - frames_written)
            for _ in range(repeat):
                proc.stdin.write(frame.tobytes())
            frames_written += repeat
            logical_idx += 1
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg exited with status {proc.returncode}")


def cli():
    try:
        filename = input("Output filename [abstract_flow.mp4]: ").strip() or "abstract_flow.mp4"
        minutes = float(input("Minutes [0]: ").strip() or 0)
        seconds = float(input("Seconds [10]: ").strip() or 10)
        width = int(input("Width [1920]: ").strip() or 1920)
        height = int(input("Height [1080]: ").strip() or 1080)
        fps = int(input("FPS [30]: ").strip() or 30)
        dup = int(input("Duplicate factor [2]: ").strip() or 2)
        run(filename, minutes, seconds, width, height, fps, dup)
        print("Done.")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def ui():
    root = tk.Tk()
    root.title("Abstract Flow")
    filename = tk.StringVar(value="media/abstract_flow.mp4")
    minutes = tk.StringVar(value="0")
    seconds = tk.StringVar(value="10")
    width = tk.StringVar(value="1920")
    height = tk.StringVar(value="1080")
    fps = tk.StringVar(value="30")
    dup = tk.StringVar(value="2")
    status = tk.StringVar(value="Idle")

    def go():
        try:
            run(
                filename.get(),
                float(minutes.get() or 0),
                float(seconds.get() or 0),
                int(width.get()),
                int(height.get()),
                int(fps.get()),
                int(dup.get()),
            )
            status.set("Done.")
            messagebox.showinfo("Abstract Flow", "Finished")
        except Exception as exc:
            status.set(f"Error: {exc}")
            messagebox.showerror("Abstract Flow", str(exc))

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    def row(label, var, r, w=16):
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=var, width=w).grid(row=r, column=1, sticky="w")

    row("Output filename", filename, 0, 28)
    row("Minutes", minutes, 1)
    row("Seconds", seconds, 2)
    row("Width", width, 3)
    row("Height", height, 4)
    row("FPS", fps, 5)
    row("Dup factor", dup, 6)

    ttk.Button(frm, text="Generate", command=go).grid(row=7, column=0, columnspan=2, pady=8)
    ttk.Label(frm, textvariable=status).grid(row=8, column=0, columnspan=2, sticky="w")
    frm.columnconfigure(1, weight=1)
    root.mainloop()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        cli()
    else:
        ui()
