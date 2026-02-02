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


def run(in_file, out_file, mode, factor, target_w, target_h, filt, crf, preset):
    if not in_file or not os.path.exists(in_file):
        raise FileNotFoundError("Input not found")

    if "." not in out_file:
        out_file += ".mp4"

    if mode == "factor":
        scale_expr = f"scale=iw*{factor}:ih*{factor}"
    else:
        scale_expr = f"scale={target_w}:{target_h}"

    scale_filter = f"{scale_expr}:flags={filt}"
    vf = scale_filter

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        in_file,
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
        out_file,
    ]
    subprocess.run(cmd, check=True)


def cli() -> None:
    inp = ask("Input video file")
    outp = ask("Output video file", "upscaled.mp4")
    mode = ask("Mode: 'factor' or 'target' resolution", "target").lower()
    if mode not in {"factor", "target"}:
        print("Mode must be 'factor' or 'target'.", file=sys.stderr)
        sys.exit(1)
    if mode == "factor":
        factor = ask("Scale factor (e.g., 2 for 2x)", "2")
        target_w = target_h = None
    else:
        target_w = ask("Target width (e.g., 3840)", "3840")
        target_h = ask("Target height (e.g., 2160)", "2160")
        factor = None
    filt = ask("Filter flags (bicubic|lanczos)", "lanczos")
    crf = ask("CRF (lower=better, 18 good)", "18")
    preset = ask("x264 preset", "slow")
    try:
        run(inp, outp, mode, factor, target_w, target_h, filt, crf, preset)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Done. Wrote {outp}")


def ui():
    import tkinter as tk
    from tkinter import filedialog, ttk, messagebox

    root = tk.Tk()
    root.title("Upscale Video")

    in_var = tk.StringVar()
    out_var = tk.StringVar(value="upscaled.mp4")
    mode_var = tk.StringVar(value="target")
    factor_var = tk.StringVar(value="2")
    w_var = tk.StringVar(value="3840")
    h_var = tk.StringVar(value="2160")
    filt_var = tk.StringVar(value="lanczos")
    crf_var = tk.StringVar(value="18")
    preset_var = tk.StringVar(value="slow")
    status = tk.StringVar(value="Idle")

    def choose_in():
        path = filedialog.askopenfilename()
        if path:
            in_var.set(path)

    def choose_out():
        path = filedialog.asksaveasfilename(defaultextension=".mp4")
        if path:
            out_var.set(path)

    def toggle_mode(*_):
        if mode_var.get() == "factor":
            factor_entry.state(["!disabled"])
            w_entry.state(["disabled"])
            h_entry.state(["disabled"])
        else:
            factor_entry.state(["disabled"])
            w_entry.state(["!disabled"])
            h_entry.state(["!disabled"])

    def go():
        try:
            run(
                in_var.get(),
                out_var.get(),
                mode_var.get(),
                factor_var.get(),
                w_var.get(),
                h_var.get(),
                filt_var.get(),
                crf_var.get(),
                preset_var.get(),
            )
            status.set("Done.")
            messagebox.showinfo("Upscale Video", "Finished")
        except Exception as exc:
            status.set(f"Error: {exc}")
            messagebox.showerror("Upscale Video", str(exc))

    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    ttk.Label(frm, text="Input").grid(row=0, column=0, sticky="w")
    ttk.Entry(frm, textvariable=in_var, width=40).grid(row=0, column=1, sticky="ew")
    ttk.Button(frm, text="Browse", command=choose_in).grid(row=0, column=2, padx=4)

    ttk.Label(frm, text="Output").grid(row=1, column=0, sticky="w")
    ttk.Entry(frm, textvariable=out_var, width=40).grid(row=1, column=1, sticky="ew")
    ttk.Button(frm, text="Save as", command=choose_out).grid(row=1, column=2, padx=4)

    ttk.Label(frm, text="Mode").grid(row=2, column=0, sticky="w")
    ttk.OptionMenu(frm, mode_var, mode_var.get(), "target", "factor", command=lambda *_: toggle_mode()).grid(
        row=2, column=1, sticky="w"
    )

    ttk.Label(frm, text="Factor").grid(row=3, column=0, sticky="w")
    factor_entry = ttk.Entry(frm, textvariable=factor_var, width=10)
    factor_entry.grid(row=3, column=1, sticky="w")

    ttk.Label(frm, text="Target W/H").grid(row=4, column=0, sticky="w")
    w_entry = ttk.Entry(frm, textvariable=w_var, width=8)
    h_entry = ttk.Entry(frm, textvariable=h_var, width=8)
    w_entry.grid(row=4, column=1, sticky="w")
    h_entry.grid(row=4, column=1, sticky="e")

    ttk.Label(frm, text="Filter").grid(row=5, column=0, sticky="w")
    ttk.Entry(frm, textvariable=filt_var, width=12).grid(row=5, column=1, sticky="w")

    ttk.Label(frm, text="CRF / Preset").grid(row=6, column=0, sticky="w")
    ttk.Entry(frm, textvariable=crf_var, width=6).grid(row=6, column=1, sticky="w")
    ttk.Entry(frm, textvariable=preset_var, width=10).grid(row=6, column=1, sticky="e")

    ttk.Button(frm, text="Upscale", command=go).grid(row=7, column=0, columnspan=3, pady=8)
    ttk.Label(frm, textvariable=status).grid(row=8, column=0, columnspan=3, sticky="w")

    for i in range(3):
        frm.columnconfigure(i, weight=1)
    toggle_mode()
    root.mainloop()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        cli()
    else:
        ui()
