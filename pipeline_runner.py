#!/usr/bin/env python3
"""
Pipeline Runner: apply a stack of common operations to one video.

Features:
- Overlays: timestamp, frame counter, watermark text.
- Optional denoise (hqdn3d) and sharpen (unsharp).
- Upscale: none, scale factor, or target resolution.
- Codec choice: libx264, libx265, h264_videotoolbox, hevc_videotoolbox.
- Audio: copy or mute.
- Optional HLS packaging after the main encode.

GUI first; CLI fallback via --cli (uses prompts).
Outputs default to media/ and remain git-ignored.
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def build_filter(scale_mode, factor, targ_w, targ_h, use_ts, use_frame, watermark, denoise, sharpen):
    filters = []
    if scale_mode == "factor":
        filters.append(f"scale=iw*{factor}:ih*{factor}:flags=lanczos")
    elif scale_mode == "target":
        filters.append(f"scale={targ_w}:{targ_h}:flags=lanczos")
    if denoise:
        filters.append("hqdn3d=2:1.5:2:1.5")
    if sharpen:
        filters.append("unsharp=5:5:0.7:5:5:0.0")
    if use_ts:
        filters.append(
            "drawtext=fontfile=/Library/Fonts/Arial.ttf:text='%{pts\\:hms}':x=10:y=10:fontsize=32:fontcolor=white@0.9:box=1:boxcolor=0x00000055"
        )
    if use_frame:
        filters.append(
            "drawtext=fontfile=/Library/Fonts/Arial.ttf:text='frame %{frame_num}':x=10:y=50:fontsize=28:fontcolor=yellow@0.9:box=1:boxcolor=0x00000055"
        )
    if watermark:
        filters.append(
            f"drawtext=fontfile=/Library/Fonts/Arial.ttf:text='{watermark}':x=w-tw-20:y=h-th-20:fontsize=32:fontcolor=white@0.85:box=1:boxcolor=0x00000055"
        )
    return ",".join(filters) if filters else None


def run_pipeline(inp, outp, scale_mode, factor, targ_w, targ_h, use_ts, use_frame, watermark, denoise, sharpen, codec, audio_copy, make_hls):
    if not os.path.exists(inp):
        raise FileNotFoundError("Input not found")
    if inp == outp:
        raise ValueError("Output must differ from input")
    if not outp.startswith("media/"):
        outp = os.path.join("media", outp)
    os.makedirs(os.path.dirname(outp), exist_ok=True)

    vf = build_filter(scale_mode, factor, targ_w, targ_h, use_ts, use_frame, watermark, denoise, sharpen)

    codec_map = {
        "libx264": ["-c:v", "libx264", "-crf", "18", "-preset", "slow"],
        "libx265": ["-c:v", "libx265", "-crf", "20", "-preset", "slow"],
        "h264_videotoolbox": ["-c:v", "h264_videotoolbox", "-b:v", "20M"],
        "hevc_videotoolbox": ["-c:v", "hevc_videotoolbox", "-b:v", "20M"],
    }
    vcodec = codec_map.get(codec, codec_map["libx264"])

    cmd = ["ffmpeg", "-y", "-i", inp]
    if vf:
        cmd += ["-vf", vf]
    cmd += vcodec
    cmd += ["-pix_fmt", "yuv420p"]
    if audio_copy:
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-an"]
    cmd.append(outp)

    subprocess.run(cmd, check=True)

    if make_hls:
        base, _ = os.path.splitext(outp)
        hls_out = base + "_hls.m3u8"
        hls_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            outp,
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-start_number",
            "0",
            "-hls_time",
            "4",
            "-hls_playlist_type",
            "vod",
            hls_out,
        ]
        subprocess.run(hls_cmd, check=True)
    return outp


def cli():
    try:
        inp = input("Input video: ").strip()
        outp = input("Output [media/output.mp4]: ").strip() or "media/output.mp4"
        mode = input("Scale mode (none/factor/target) [none]: ").strip() or "none"
        factor = input("Factor (if factor mode) [2]: ").strip() or "2"
        targ_w = input("Target width [3840]: ").strip() or "3840"
        targ_h = input("Target height [2160]: ").strip() or "2160"
        use_ts = (input("Timestamp overlay? (y/N): ").strip().lower() == "y")
        use_frame = (input("Frame counter? (y/N): ").strip().lower() == "y")
        watermark = input("Watermark text (blank=none): ").strip()
        denoise = (input("Denoise? (y/N): ").strip().lower() == "y")
        sharpen = (input("Sharpen? (y/N): ").strip().lower() == "y")
        codec = input("Codec (libx264/libx265/h264_videotoolbox/hevc_videotoolbox) [libx264]: ").strip() or "libx264"
        audio_copy = (input("Copy audio? (Y/n): ").strip().lower() != "n")
        make_hls = (input("Also make HLS? (y/N): ").strip().lower() == "y")
        run_pipeline(
            inp,
            outp,
            mode,
            factor,
            targ_w,
            targ_h,
            use_ts,
            use_frame,
            watermark,
            denoise,
            sharpen,
            codec,
            audio_copy,
            make_hls,
        )
        print("Done.")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Pipeline Runner")
        self.build_ui()

    def choose_in(self):
        path = filedialog.askopenfilename(initialdir="media", filetypes=[("Videos", "*.mp4 *.mov *.mkv *.webm")])
        if path:
            self.in_var.set(path)

    def choose_out(self):
        path = filedialog.asksaveasfilename(initialdir="media", defaultextension=".mp4")
        if path:
            self.out_var.set(path)

    def go(self):
        try:
            out = run_pipeline(
                self.in_var.get(),
                self.out_var.get(),
                self.scale_mode.get(),
                self.factor_var.get(),
                self.w_var.get(),
                self.h_var.get(),
                self.ts_var.get(),
                self.frame_var.get(),
                self.wm_var.get(),
                self.denoise_var.get(),
                self.sharp_var.get(),
                self.codec_var.get(),
                self.audio_var.get(),
                self.hls_var.get(),
            )
            messagebox.showinfo("Pipeline Runner", f"Finished:\n{out}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def build_ui(self):
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar(value="media/output.mp4")
        self.scale_mode = tk.StringVar(value="none")
        self.factor_var = tk.StringVar(value="2")
        self.w_var = tk.StringVar(value="3840")
        self.h_var = tk.StringVar(value="2160")
        self.ts_var = tk.BooleanVar(value=False)
        self.frame_var = tk.BooleanVar(value=False)
        self.wm_var = tk.StringVar(value="")
        self.denoise_var = tk.BooleanVar(value=False)
        self.sharp_var = tk.BooleanVar(value=False)
        self.codec_var = tk.StringVar(value="libx264")
        self.audio_var = tk.BooleanVar(value=True)
        self.hls_var = tk.BooleanVar(value=False)

        ttk.Label(frm, text="Input").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.in_var, width=50).grid(row=0, column=1, sticky="ew")
        ttk.Button(frm, text="Browse", command=self.choose_in).grid(row=0, column=2, padx=4)

        ttk.Label(frm, text="Output").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.out_var, width=50).grid(row=1, column=1, sticky="ew")
        ttk.Button(frm, text="Save as", command=self.choose_out).grid(row=1, column=2, padx=4)

        ttk.Label(frm, text="Scale mode").grid(row=2, column=0, sticky="w")
        ttk.OptionMenu(frm, self.scale_mode, "none", "none", "factor", "target").grid(row=2, column=1, sticky="w")
        scale_frame = ttk.Frame(frm)
        scale_frame.grid(row=3, column=1, sticky="w")
        ttk.Label(scale_frame, text="Factor").grid(row=0, column=0, sticky="w")
        ttk.Entry(scale_frame, textvariable=self.factor_var, width=6).grid(row=0, column=1, padx=4)
        ttk.Label(scale_frame, text="Target W/H").grid(row=0, column=2, padx=(8, 0))
        ttk.Entry(scale_frame, textvariable=self.w_var, width=7).grid(row=0, column=3, padx=2)
        ttk.Entry(scale_frame, textvariable=self.h_var, width=7).grid(row=0, column=4, padx=2)

        ttk.Checkbutton(frm, text="Timestamp", variable=self.ts_var).grid(row=4, column=0, sticky="w")
        ttk.Checkbutton(frm, text="Frame counter", variable=self.frame_var).grid(row=4, column=1, sticky="w")
        ttk.Label(frm, text="Watermark").grid(row=5, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.wm_var, width=30).grid(row=5, column=1, sticky="w")

        ttk.Checkbutton(frm, text="Denoise (hqdn3d)", variable=self.denoise_var).grid(row=6, column=0, sticky="w")
        ttk.Checkbutton(frm, text="Sharpen (unsharp)", variable=self.sharp_var).grid(row=6, column=1, sticky="w")

        ttk.Label(frm, text="Codec").grid(row=7, column=0, sticky="w")
        ttk.OptionMenu(frm, self.codec_var, "libx264", "libx264", "libx265", "h264_videotoolbox", "hevc_videotoolbox").grid(
            row=7, column=1, sticky="w"
        )

        ttk.Checkbutton(frm, text="Copy audio", variable=self.audio_var).grid(row=8, column=0, sticky="w")
        ttk.Checkbutton(frm, text="Also make HLS", variable=self.hls_var).grid(row=8, column=1, sticky="w")

        ttk.Button(frm, text="Run", command=self.go).grid(row=9, column=0, columnspan=3, pady=10, sticky="ew")

        for c in range(3):
            frm.columnconfigure(c, weight=1)


def main():
    if "--cli" in sys.argv:
        cli()
    else:
        App().root.mainloop()


if __name__ == "__main__":
    main()
