#!/usr/bin/env python3
"""
Workflow Builder

Lightweight node canvas to chain the existing tools visually.
- Add nodes from the tool list, drag to position.
- Lines auto-connect in the order shown in the side list (and update when re-ordered).
- Run workflow launches each tool sequentially (opens their own UIs).

Note: Tools that require CLI params will still show their UI when launched.
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


class Node:
    def __init__(self, canvas: tk.Canvas, label: str, script: str, x=80, y=80):
        self.canvas = canvas
        self.label = label
        self.script = script
        self.x = x
        self.y = y
        self.w = 140
        self.h = 50
        self.rect = canvas.create_rectangle(x, y, x + self.w, y + self.h, fill="#222a38", outline="#7fb0ff", width=2)
        self.text = canvas.create_text(x + self.w / 2, y + self.h / 2, text=label, fill="white")
        self.canvas.tag_bind(self.rect, "<ButtonPress-1>", self.start_drag)
        self.canvas.tag_bind(self.text, "<ButtonPress-1>", self.start_drag)
        self.canvas.tag_bind(self.rect, "<B1-Motion>", self.drag)
        self.canvas.tag_bind(self.text, "<B1-Motion>", self.drag)

    def start_drag(self, event):
        self._drag_start = (event.x, event.y)

    def drag(self, event):
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self.canvas.move(self.rect, dx, dy)
        self.canvas.move(self.text, dx, dy)
        self.x += dx
        self.y += dy
        self._drag_start = (event.x, event.y)

    def center(self):
        return (self.x + self.w / 2, self.y + self.h / 2)


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Workflow Builder")
        self.nodes = []
        self.lines = []
        self.build_ui()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Left panel: canvas
        self.canvas = tk.Canvas(main, width=640, height=480, bg="#0f121a")
        self.canvas.grid(row=0, column=0, rowspan=4, sticky="nsew", padx=(0, 8))
        main.columnconfigure(0, weight=3)
        main.rowconfigure(0, weight=1)

        # Right panel
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="ns")
        main.columnconfigure(1, weight=0)

        ttk.Label(right, text="Add Node").grid(row=0, column=0, sticky="w")
        self.tool_var = tk.StringVar(value=TOOLS[0][0])
        ttk.OptionMenu(right, self.tool_var, TOOLS[0][0], *[t[0] for t in TOOLS]).grid(row=1, column=0, sticky="ew")
        ttk.Button(right, text="Add", command=self.add_node).grid(row=2, column=0, pady=4, sticky="ew")

        ttk.Label(right, text="Run Order").grid(row=3, column=0, sticky="w", pady=(12, 0))
        self.listbox = tk.Listbox(right, height=12, width=28)
        self.listbox.grid(row=4, column=0, sticky="nsew")
        move_frame = ttk.Frame(right)
        move_frame.grid(row=5, column=0, pady=4)
        ttk.Button(move_frame, text="Up", command=self.move_up, width=6).grid(row=0, column=0, padx=2)
        ttk.Button(move_frame, text="Down", command=self.move_down, width=6).grid(row=0, column=1, padx=2)

        ttk.Button(right, text="Run Workflow", command=self.run_workflow).grid(row=6, column=0, pady=8, sticky="ew")
        self.status = tk.StringVar(value="Idle")
        ttk.Label(right, textvariable=self.status).grid(row=7, column=0, sticky="w")

        for i in range(8):
            right.rowconfigure(i, weight=0)
        right.rowconfigure(4, weight=1)

    def add_node(self):
        label = self.tool_var.get()
        script = dict(TOOLS)[label]
        node = Node(self.canvas, label, script, x=80 + 20 * len(self.nodes), y=80 + 20 * len(self.nodes))
        self.nodes.append(node)
        self.listbox.insert(tk.END, label)
        self.redraw_lines()

    def move_up(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == 0:
            return
        self.listbox.delete(idx)
        self.listbox.insert(idx - 1, self.nodes[idx].label)
        self.nodes[idx - 1], self.nodes[idx] = self.nodes[idx], self.nodes[idx - 1]
        self.listbox.selection_set(idx - 1)
        self.redraw_lines()

    def move_down(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == self.listbox.size() - 1:
            return
        self.listbox.delete(idx)
        self.listbox.insert(idx + 1, self.nodes[idx].label)
        self.nodes[idx], self.nodes[idx + 1] = self.nodes[idx + 1], self.nodes[idx]
        self.listbox.selection_set(idx + 1)
        self.redraw_lines()

    def redraw_lines(self):
        for line in self.lines:
            self.canvas.delete(line)
        self.lines.clear()
        for i in range(len(self.nodes) - 1):
            x1, y1 = self.nodes[i].center()
            x2, y2 = self.nodes[i + 1].center()
            line = self.canvas.create_line(x1, y1, x2, y2, fill="#6bc1ff", width=2, arrow=tk.LAST)
            self.lines.append(line)

    def run_workflow(self):
        if not self.nodes:
            messagebox.showerror("No steps", "Add at least one node.")
            return
        self.status.set("Running...")
        self.root.update_idletasks()
        for node in self.nodes:
            script = node.script
            if not os.path.exists(script):
                messagebox.showerror("Missing", f"{script} not found.")
                self.status.set("Missing script.")
                return
            try:
                subprocess.Popen([sys.executable, script])
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Launch failed", str(exc))
                self.status.set("Error.")
                return
        self.status.set("Launched all steps.")


def main():
    App().root.mainloop()


if __name__ == "__main__":
    main()
