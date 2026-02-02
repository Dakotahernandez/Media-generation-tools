#!/usr/bin/env python3
"""
Bouncing ball generator.

Features:
- Single ball with random initial color that changes on each bounce.
- Simple physics with elastic wall bounces.
- Prompts for duration, resolution (max 3840x2160), FPS, ball radius, speed, and frame-duplication factor to reduce CPU.
- Streams raw frames to ffmpeg (H.264 MP4).
"""

import math
import subprocess
import sys
from typing import Tuple

import numpy as np


def ask_int(prompt: str, default: int, min_val: int | None = None) -> int:
    raw = input(prompt).strip()
    val = default if raw == "" else int(raw)
    if min_val is not None and val < min_val:
        raise ValueError(f"{prompt.strip()} must be >= {min_val}")
    return val


def ask_float(prompt: str, default: float, min_val: float | None = None) -> float:
    raw = input(prompt).strip()
    val = default if raw == "" else float(raw)
    if min_val is not None and val < min_val:
        raise ValueError(f"{prompt.strip()} must be >= {min_val}")
    return val


def random_color(rng: np.random.Generator) -> np.ndarray:
    return rng.integers(60, 256, size=3, dtype=np.uint8)


def main() -> None:
    try:
        filename = input("Output filename [bouncing_ball.mp4]: ").strip() or "bouncing_ball.mp4"
        if "." not in filename:
            filename += ".mp4"
        minutes = ask_float("Length minutes [0]: ", 0.0, 0.0)
        seconds = ask_float("Length seconds [10]: ", 10.0, 0.0)
        width = ask_int("Width [1920]: ", 1920, 1)
        height = ask_int("Height [1080]: ", 1080, 1)
        fps = ask_int("FPS [30]: ", 30, 1)
        dup = ask_int("Frame duplicate factor [1]: ", 1, 1)
        radius = ask_int("Ball radius px [40]: ", 40, 2)
        speed = ask_float("Speed px/sec [450]: ", 450.0, 1.0)
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
        print("ffmpeg not found on PATH.", file=sys.stderr)
        sys.exit(1)

    rng = np.random.default_rng()

    # Initial state
    x = rng.uniform(radius, width - radius)
    y = rng.uniform(radius, height - radius)
    angle = rng.uniform(0, 2 * math.pi)
    vx = math.cos(angle) * speed
    vy = math.sin(angle) * speed
    color = random_color(rng)

    # Precompute circle mask offsets
    diam = 2 * radius + 1
    yy, xx = np.ogrid[-radius : radius + 1, -radius : radius + 1]
    mask = xx * xx + yy * yy <= radius * radius
    rel_rows, rel_cols = np.where(mask)
    rel_rows -= radius
    rel_cols -= radius

    try:
        frames_written = 0
        while frames_written < target_frames:
            # Physics step
            x += vx / fps
            y += vy / fps

            bounced = False
            if x < radius:
                x = radius
                vx = abs(vx)
                bounced = True
            elif x > width - radius:
                x = width - radius
                vx = -abs(vx)
                bounced = True
            if y < radius:
                y = radius
                vy = abs(vy)
                bounced = True
            elif y > height - radius:
                y = height - radius
                vy = -abs(vy)
                bounced = True

            if bounced:
                color = random_color(rng)

            frame = np.zeros((height, width, 3), dtype=np.uint8)
            cx, cy = int(round(x)), int(round(y))
            rows = cy + rel_rows
            cols = cx + rel_cols
            valid = (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
            frame[rows[valid], cols[valid]] = color

            repeat = min(dup, target_frames - frames_written)
            for _ in range(repeat):
                proc.stdin.write(frame.tobytes())
            frames_written += repeat
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()

    if proc.returncode == 0:
        print(f"Done. Saved {total_seconds:.2f}s to {filename}")
    else:
        print(f"ffmpeg exited with status {proc.returncode}", file=sys.stderr)


if __name__ == "__main__":
    main()
