#!/usr/bin/env python3
"""
Black-hole spiral generator.

Visuals:
- A solid black core (event horizon) in the center.
- Colored material spirals inward; near the horizon it stretches tangentially,
  loses saturation, and fades to black as it crosses the boundary.
- Uses a procedural shader per frame and optional frame duplication to reduce CPU load.

Inputs (prompted):
- Output filename
- Length (minutes + seconds)
- Resolution (max 3840x2160)
- FPS
- Frame duplicate factor (repeat each computed frame N times)

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


def ask_bool(prompt: str, default: bool = False) -> bool:
    raw = input(prompt + (" [Y/n]: " if default else " [y/N]: ")).strip().lower()
    if raw == "":
        return default
    return raw in ("y", "yes")


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
        filename = input("Output filename [spiral_black_hole.mp4]: ").strip() or "spiral_black_hole.mp4"
        if "." not in filename:
            filename += ".mp4"
        minutes = ask_float("Length minutes [0]: ", 0.0, 0.0)
        seconds = ask_float("Length seconds [10]: ", 10.0, 0.0)
        width = ask_int("Width [1920]: ", 1920, 1)
        height = ask_int("Height [1080]: ", 1080, 1)
        fps = ask_int("FPS [30]: ", 30, 1)
        dup_factor = ask_int("Frame duplicate factor [3]: ", 3, 1)
        add_objects = ask_bool("Add random infalling objects?", default=False)
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

    # Normalized, aspect-corrected coordinates centered at 0.
    x = np.linspace(-1.0, 1.0, width, dtype=np.float32)
    y = np.linspace(-1.0, 1.0, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    aspect = width / height
    xx *= aspect
    r = np.sqrt(xx * xx + yy * yy) + 1e-6
    theta = np.arctan2(yy, xx)

    # Event horizon radius and soft falloff.
    horizon = 0.28
    fade_width = 0.08

    # Spiral dynamics (black hole size remains constant).
    swirl_rate = 1.2       # global angular speed (rad/s)
    swirl_shear = 3.0      # extra twist near center
    flow_speed = 0.35      # perceived inward flow factor (affects sampling only)
    hue_speed = np.random.uniform(0.15, 0.45)  # hue cycles per second
    base_hue = np.random.random()
    jitter_amp = 0.04
    stretch_power = 1.6    # tangential stretch factor near horizon

    # Infalling objects setup
    num_objs = 40 if add_objects else 0
    obj_rad_min = 0.02
    obj_rad_max = 0.9
    obj_speed_min = 0.12
    obj_speed_max = 0.35
    obj_size_px = (1, 3)

    if add_objects:
        rng = np.random.default_rng()
        obj_r = rng.uniform(obj_rad_min, obj_rad_max, size=num_objs)
        obj_theta = rng.uniform(-math.pi, math.pi, size=num_objs)
        obj_speed = rng.uniform(obj_speed_min, obj_speed_max, size=num_objs)
        obj_color = rng.uniform(0.6, 1.0, size=(num_objs, 3)) * 255.0
        obj_size = rng.integers(obj_size_px[0], obj_size_px[1] + 1, size=num_objs)
    else:
        rng = np.random.default_rng()
    try:
        frames_written = 0
        logical_idx = 0
        while frames_written < target_frames:
            t = logical_idx / fps

            # Spiral mapping.
            # Keep physical radius fixed; create inward motion by animating sampling phase.
            radial = r
            angle = theta - swirl_rate * t - swirl_shear / (1.2 + r) - flow_speed * radial * t

            # Stretch tangentially near the horizon: scale angular component.
            stretch = 1.0 + (np.exp(-(radial / horizon) ** stretch_power) * 3.0)
            angle_stretched = angle * stretch

            # Hue field.
            hue = (base_hue + hue_speed * t + angle_stretched / (2 * math.pi) - flow_speed * radial * t) % 1.0
            hue += np.sin(7 * radial + t) * jitter_amp
            hue %= 1.0

            # Saturation drops inside the horizon and toward center.
            sat = np.clip(1.0 - np.exp(-((radial - horizon) / fade_width)), 0.0, 1.0)
            sat = np.where(radial < horizon, 0.2 * (radial / horizon), sat)

            # Value bright outside, dark inside.
            val = np.exp(-2.0 * radial) * 0.9
            val = np.where(radial < horizon, val * (radial / horizon), val)

            rgb = hsv_to_rgb(hue, sat, val)

            if add_objects and num_objs > 0:
                # Update object positions (inward drift and swirl)
                obj_r -= obj_speed * (1.0 / fps)
                obj_theta += swirl_rate * (1.0 / fps)

                # Respawn objects that crossed the horizon
                crossed = obj_r < horizon
                if np.any(crossed):
                    obj_r[crossed] = rng.uniform(obj_rad_max * 0.6, obj_rad_max, size=np.count_nonzero(crossed))
                    obj_theta[crossed] = rng.uniform(-math.pi, math.pi, size=np.count_nonzero(crossed))
                    obj_speed[crossed] = rng.uniform(obj_speed_min, obj_speed_max, size=np.count_nonzero(crossed))
                    obj_color[crossed] = rng.uniform(0.6, 1.0, size=(np.count_nonzero(crossed), 3)) * 255.0
                    obj_size[crossed] = rng.integers(obj_size_px[0], obj_size_px[1] + 1, size=np.count_nonzero(crossed))

                # Draw objects (simple square splats)
                xx_obj = obj_r * np.cos(obj_theta)
                yy_obj = obj_r * np.sin(obj_theta)
                cols = ((xx_obj / aspect + 1.0) * 0.5 * (width - 1)).astype(int)
                rows = ((yy_obj + 1.0) * 0.5 * (height - 1)).astype(int)
                cols = np.clip(cols, 0, width - 1)
                rows = np.clip(rows, 0, height - 1)
                for i in range(num_objs):
                    s = obj_size[i]
                    r0 = max(0, rows[i] - s)
                    r1 = min(height, rows[i] + s + 1)
                    c0 = max(0, cols[i] - s)
                    c1 = min(width, cols[i] + s + 1)
                    rgb[r0:r1, c0:c1] = np.clip(rgb[r0:r1, c0:c1].astype(np.uint16) + obj_color[i].astype(np.uint16), 0, 255)

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
