#!/usr/bin/env python3
"""
Simple ffmpeg-powered image upscaler.

Prompts for:
- Input image
- Output image
- Mode: scale factor or target resolution
- Filter: bicubic (default) or lanczos

Keeps alpha for PNG/WebP. Requires ffmpeg on PATH.
"""

import os
import subprocess
import sys


def ask(prompt: str, default: str | None = None) -> str:
    raw = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return raw or (default or "")


def main() -> None:
    inp = ask("Input image file")
    if not inp:
        print("Input is required.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(inp):
        print("Input not found.", file=sys.stderr)
        sys.exit(1)

    outp = ask("Output image file", "upscaled.png")
    if "." not in outp:
        outp += ".png"

    mode = ask("Mode: 'factor' or 'target' resolution", "factor").lower()
    if mode not in {"factor", "target"}:
        print("Mode must be 'factor' or 'target'.", file=sys.stderr)
        sys.exit(1)

    if mode == "factor":
        factor = ask("Scale factor (e.g., 2 for 2x)", "2")
        scale_expr = f"scale=iw*{factor}:ih*{factor}"
    else:
        target_w = ask("Target width", "3840")
        target_h = ask("Target height", "2160")
        scale_expr = f"scale={target_w}:{target_h}"

    filt = ask("Filter flags (bicubic|lanczos)", "lanczos")
    vf = f"{scale_expr}:flags={filt}"

    # Preserve alpha by default; let ffmpeg pick codec from extension.
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        inp,
        "-vf",
        vf,
        "-c:v",
        "png" if outp.lower().endswith(".png") else "libwebp" if outp.lower().endswith(".webp") else "mjpeg",
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
