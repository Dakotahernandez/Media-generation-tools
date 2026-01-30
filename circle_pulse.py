#!/usr/bin/env python3
"""
Generate a "black hole" vortex video: swirling inward motion that pulls in
continuously changing colors. Uses a procedural shader per frame, then
duplicates frames to keep CPU load manageable.

Inputs (prompted):
- Output filename
- Length (minutes + seconds)
- Resolution (width/height, max 3840x2160)
- FPS
- Duplicate factor (how many times to repeat each computed frame)

Requires: Python 3, numpy, ffmpeg on PATH.
"""

import math
import subprocess
import sys
from typing import Tuple

import numpy as np


def ask_float(prompt: str, default: float, min_val: float | None = None) -> float:
    raw = input(prompt).strip()
    val = default if raw == "" else float(raw)
    if min_val is not None and val < min_val:
        raise ValueError(f"{prompt.strip()} must be >= {min_val}")
    return val


def ask_int(prompt: str, default: int, min_val: int | None = None) -> int:
    raw = input(prompt).strip()
    val = default if raw == "" else int(raw)
    if min_val is not None and val < min_val:
        raise ValueError(f"{prompt.strip()} must be >= {min_val}")
    return val


def hsv_to_rgb(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Vectorized HSV (0-1) to RGB (0-255 uint8)."""
    i = np.floor(h * 6).astype(np.int32)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)

    r = np.choose(i % 6, [v, q, p, p, t, v])
    g = np.choose(i % 6, [t, v, v, q, p, p])
    b = np.choose(i % 6, [p, p, t, v, v, q])

    rgb = np.stack([r, g, b], axis=-1)
    rgb = np.clip(rgb * 255.0, 0, 255).astype(np.uint8)
    return rgb


def main() -> None:
    try:
        filename = input("Output filename [black_hole.mp4]: ").strip() or "black_hole.mp4"
        if "." not in filename:
            filename += ".mp4"
        minutes = ask_float("Length minutes [0]: ", 0.0, 0.0)
        seconds = ask_float("Length seconds [10]: ", 10.0, 0.0)
        width = ask_int("Width [1920]: ", 1920, 1)
        height = ask_int("Height [1080]: ", 1080, 1)
        fps = ask_int("FPS [30]: ", 30, 1)
        dup_factor = ask_int("Frame duplicate factor [3]: ", 3, 1)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    if width > 3840 or height > 2160:
        print("Max resolution is 3840x2160.", file=sys.stderr)
        sys.exit(1)

    total_seconds = minutes * 60 + seconds
    if total_seconds <= 0:
        print("Length must be greater than zero.", file=sys.stderr)
        sys.exit(1)

    target_frames = int(math.ceil(total_seconds * fps))
    logical_frames = math.ceil(target_frames / dup_factor)

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
        print("ffmpeg not found on PATH. Install ffmpeg and try again.", file=sys.stderr)
        sys.exit(1)

    # Normalized coordinate grid centered at 0 with aspect correction.
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    aspect = width / height
    xx *= aspect
    r = np.sqrt(xx * xx + yy * yy) + 1e-6
    theta = np.arctan2(yy, xx)

    # Base parameters for the vortex motion.
    swirl_rate = 0.7  # radians per second
    swirl_strength = 2.5  # additional twist near center
    zoom_rate = 0.18  # inward drift per second
    hue_speed = 0.22  # hue cycles per second
    pulsate = 3.0  # brightness pulsation Hz

    try:
        frames_written = 0
        logical_idx = 0
        while frames_written < target_frames:
            t = logical_idx / fps

            # Time-evolving angle and radius.
            angle = theta - swirl_rate * t - swirl_strength * (1.0 / (1.5 + r))
            scale = np.exp(-zoom_rate * t)
            r_scaled = r * scale

            # Hue varies with angle and time; small jitter for randomness.
            hue = (hue_speed * t + angle / (2 * math.pi)) % 1.0
            hue += np.sin(5 * r_scaled + t * 0.5) * 0.03
            hue %= 1.0

            sat = np.clip(0.7 + 0.3 * np.sin(3 * r + t), 0.0, 1.0)
            val = np.exp(-2.5 * r_scaled)  # bright at center, dark edges
            val *= 0.7 + 0.3 * (0.5 + 0.5 * np.sin(2 * math.pi * pulsate * t - 6 * r))

            # Convert HSV -> RGB
            rgb = hsv_to_rgb(hue, sat, val)

            # Write duplicated frames.
            repeat = min(dup_factor, target_frames - frames_written)
            for _ in range(repeat):
                proc.stdin.write(rgb.tobytes())
            frames_written += repeat
            logical_idx += 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()

    if proc.returncode == 0:
        print(f"Done. Saved {total_seconds:.1f}s video to {filename}")
    else:
        print(f"ffmpeg exited with status {proc.returncode}", file=sys.stderr)


if __name__ == "__main__":
    main()
