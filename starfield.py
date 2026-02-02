#!/usr/bin/env python3
"""
Space starfield generator.

Features:
- 2D starfield with depth: stars have different speeds and brightness.
- When a star exits the left edge, it respawns on the right with new depth/brightness/color.
- Optional subtle hue shift for a galactic vibe.
- Frame duplication option to reduce CPU load.

Prompts for: filename, duration, resolution (max 3840x2160), FPS, number of stars, duplication factor.

Requires: Python 3, numpy, ffmpeg on PATH.
"""

import math
import subprocess
import sys

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


def main() -> None:
    try:
        filename = input("Output filename [starfield.mp4]: ").strip() or "starfield.mp4"
        if "." not in filename:
            filename += ".mp4"
        minutes = ask_float("Length minutes [0]: ", 0.0, 0.0)
        seconds = ask_float("Length seconds [10]: ", 10.0, 0.0)
        width = ask_int("Width [1920]: ", 1920, 1)
        height = ask_int("Height [1080]: ", 1080, 1)
        fps = ask_int("FPS [30]: ", 30, 1)
        dup = ask_int("Frame duplicate factor [1]: ", 1, 1)
        n_stars = ask_int("Number of stars [500]: ", 500, 1)
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

    # Star properties
    x = rng.uniform(0, width, size=n_stars).astype(np.float32)
    y = rng.uniform(0, height, size=n_stars).astype(np.float32)
    depth = rng.uniform(0.2, 1.0, size=n_stars).astype(np.float32)  # nearer == faster/brighter
    speed = (60.0 + 340.0 * depth).astype(np.float32)  # px/s
    hue = rng.random(size=n_stars).astype(np.float32) * 0.15  # slight color tint
    sat = rng.uniform(0.0, 0.25, size=n_stars).astype(np.float32)
    val = (0.4 + 0.6 * depth).astype(np.float32)
    size = rng.integers(1, 3, size=n_stars, dtype=np.int32)  # pixel size

    try:
        frames_written = 0
        while frames_written < target_frames:
            # Update positions
            x -= speed / fps
            wrap = x < -3  # allow small overshoot
            if np.any(wrap):
                count = int(np.count_nonzero(wrap))
                x[wrap] = width + rng.uniform(0, 5, size=count)
                y[wrap] = rng.uniform(0, height, size=count)
                depth[wrap] = rng.uniform(0.2, 1.0, size=count)
                speed[wrap] = 60.0 + 340.0 * depth[wrap]
                hue[wrap] = rng.random(size=count) * 0.15 + rng.random() * 0.2
                sat[wrap] = rng.uniform(0.0, 0.25, size=count)
                val[wrap] = 0.4 + 0.6 * depth[wrap]
                size[wrap] = rng.integers(1, 3, size=count)

            frame = np.zeros((height, width, 3), dtype=np.uint8)

            # Draw stars
            cols = x.astype(np.int32)
            rows = y.astype(np.int32)
            mask = (cols >= 0) & (cols < width) & (rows >= 0) & (rows < height)
            cols = cols[mask]
            rows = rows[mask]
            if cols.size:
                rgb = hsv_to_rgb(hue[mask], sat[mask], val[mask]) * 255.0
                rgb = np.clip(rgb, 0, 255).astype(np.uint8)
                for i in range(cols.size):
                    s = size[mask][i]
                    r0 = max(0, rows[i] - s)
                    r1 = min(height, rows[i] + s + 1)
                    c0 = max(0, cols[i] - s)
                    c1 = min(width, cols[i] + s + 1)
                    frame[r0:r1, c0:c1] = rgb[i]

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
