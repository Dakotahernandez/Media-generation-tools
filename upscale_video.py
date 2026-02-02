#!/usr/bin/env python3
"""
Simple ffmpeg-powered video upscaler.

Prompts for:
- Input path
- Output path
- Mode: target resolution or scale factor
- Filter: bicubic (default) or lanczos

Audio is copied. Video encoded with H.264 (libx264) CRF 18 preset slow by default.
Requires ffmpeg on PATH.
"""

import os
import subprocess
import sys


def ask(prompt: str, default: str | None = None) -> str:
    raw = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return raw or (default or "")


def main() -> None:
    inp = ask("Input video file")
    if not inp:
        print("Input is required.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(inp):
        print("Input not found.", file=sys.stderr)
        sys.exit(1)

    outp = ask("Output video file", "upscaled.mp4")
    if "." not in outp:
        outp += ".mp4"

    mode = ask("Mode: 'factor' or 'target' resolution", "target").lower()
    if mode not in {"factor", "target"}:
        print("Mode must be 'factor' or 'target'.", file=sys.stderr)
        sys.exit(1)

    if mode == "factor":
        factor = ask("Scale factor (e.g., 2 for 2x)", "2")
        scale_expr = f"scale=iw*{factor}:ih*{factor}"
    else:
        target_w = ask("Target width (e.g., 3840)", "3840")
        target_h = ask("Target height (e.g., 2160)", "2160")
        scale_expr = f"scale={target_w}:{target_h}"

    filt = ask("Filter flags (bicubic|lanczos)", "lanczos")
    scale_filter = f"{scale_expr}:flags={filt}"

    crf = ask("CRF (lower=better, 18 good)", "18")
    preset = ask("x264 preset", "slow")

    vf = scale_filter

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        inp,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-crf",
        crf,
        "-preset",
        preset,
        "-c:a",
        "copy",
        outp,
    ]

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print("ffmpeg not found on PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"ffmpeg failed: {exc}", file=sys.stderr)
        sys.exit(exc.returncode)

    print(f"Done. Wrote {outp}")


if __name__ == "__main__":
    main()
