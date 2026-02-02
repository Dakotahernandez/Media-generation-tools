#!/usr/bin/env python3
"""
Media Suite launcher: one window to open any of the generators/upscalers.
Opens each tool in its own process using the current Python interpreter.
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox


TOOLS = [
    ("Circle Pulse", "circle_pulse.py"),
    ("Spiral Black Hole", "spiral_black_hole.py"),
    ("Gradient Cycle", "gradient_cycle.py"),
    ("Color Cycle 4K", "color_cycle_4k.py"),
    ("Bouncing Ball", "bouncing_ball.py"),
    ("Starfield", "starfield.py"),
    ("Abstract Flow", "abstract_flow.py"),
    ("Upscale Video", "upscale_video.py"),
    ("Upscale Image", "upscale_image.py"),
    ("Batch Runner", "batch_runner.py"),
]


def launch(script: str):
    if not os.path.exists(script):
        messagebox.showerror("Not found", f"{script} missing.")
        return
    try:
        subprocess.Popen([sys.executable, script])
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror("Launch failed", str(exc))


def main():
    root = tk.Tk()
    root.title("Media Suite")
    frm = ttk.Frame(root, padding=12)
    frm.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    ttk.Label(frm, text="Generators & Tools").grid(row=0, column=0, sticky="w")
    for idx, (label, script) in enumerate(TOOLS, start=1):
        ttk.Button(frm, text=label, command=lambda s=script: launch(s)).grid(row=idx, column=0, sticky="ew", pady=2)

    ttk.Button(frm, text="Quit", command=root.destroy).grid(row=len(TOOLS) + 1, column=0, pady=8, sticky="e")
    frm.columnconfigure(0, weight=1)
    root.mainloop()


if __name__ == "__main__":
    main()
