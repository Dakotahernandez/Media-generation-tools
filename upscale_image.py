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


def run(inp, outp, mode, factor, target_w, target_h, filt):
    if not inp or not os.path.exists(inp):
        raise FileNotFoundError("Input not found")
    if "." not in outp:
        outp += ".png"
    if mode == "factor":
        scale_expr = f"scale=iw*{factor}:ih*{factor}"
    else:
        scale_expr = f"scale={target_w}:{target_h}"
    vf = f"{scale_expr}:flags={filt}"
    codec = "png" if outp.lower().endswith(".png") else "libwebp" if outp.lower().endswith(".webp") else "mjpeg"
    cmd = ["ffmpeg", "-y", "-i", inp, "-vf", vf, "-c:v", codec, outp]
    subprocess.run(cmd, check=True)


def cli():
    inp = ask("Input image file")
    outp = ask("Output image file", "upscaled.png")
    mode = ask("Mode: 'factor' or 'target' resolution", "factor").lower()
    if mode not in {"factor", "target"}:
        print("Mode must be 'factor' or 'target'.", file=sys.stderr)
        sys.exit(1)
    if mode == "factor":
        factor = ask("Scale factor (e.g., 2 for 2x)", "2")
        target_w = target_h = None
    else:
        target_w = ask("Target width", "3840")
        target_h = ask("Target height", "2160")
        factor = None
    filt = ask("Filter flags (bicubic|lanczos)", "lanczos")
    try:
        run(inp, outp, mode, factor, target_w, target_h, filt)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Done. Wrote {outp}")


def ui():
    import tkinter as tk
    from tkinter import filedialog, ttk, messagebox

    root = tk.Tk()
    root.title("Upscale Image")

    in_var = tk.StringVar()
    out_var = tk.StringVar(value="upscaled.png")
    mode_var = tk.StringVar(value="factor")
    factor_var = tk.StringVar(value="2")
    w_var = tk.StringVar(value="3840")
    h_var = tk.StringVar(value="2160")
    filt_var = tk.StringVar(value="lanczos")
    status = tk.StringVar(value="Idle")

    def choose_in():
        path = filedialog.askopenfilename()
        if path:
            in_var.set(path)

    def choose_out():
        path = filedialog.asksaveasfilename(defaultextension=".png")
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
            )
            status.set("Done.")
            messagebox.showinfo("Upscale Image", "Finished")
        except Exception as exc:
            status.set(f"Error: {exc}")
            messagebox.showerror("Upscale Image", str(exc))

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
    ttk.OptionMenu(frm, mode_var, mode_var.get(), "factor", "target", command=lambda *_: toggle_mode()).grid(
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

    ttk.Button(frm, text="Upscale", command=go).grid(row=6, column=0, columnspan=3, pady=8)
    ttk.Label(frm, textvariable=status).grid(row=7, column=0, columnspan=3, sticky="w")

    for i in range(3):
        frm.columnconfigure(i, weight=1)
    toggle_mode()
    root.mainloop()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        cli()
    else:
        ui()
