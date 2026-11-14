#!/usr/bin/env python3
"""
gui.py - Modern Graphical User Interface for FPS Converter.

Features:
- Native Windows/macOS/Linux file picker for selecting one or more video files.
- Real-time percentage progress bar, encoding speed (e.g., 14.5x), and elapsed time.
- GPU backend auto-detection and hardware testing.
- Target FPS preset buttons (24, 30, 60, 120, 144) and custom FPS entry.
- Fast duplicate vs motion interpolation modes.
- Output directory selector and 'Open Output Folder' shortcut.
- Threaded execution with safe cancellation.
"""
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import fps_converter

# Enable high DPI awareness on Windows
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


class FpsConverterGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FPS Converter - GPU Frame Rate Transcoder")
        self.geometry("860x740")
        self.minsize(780, 640)

        # Application state
        self.selected_files: list[Path] = []
        self.is_converting = False
        self.stop_event = threading.Event()
        self.msg_queue = queue.Queue()

        self.apply_theme()
        self.build_ui()
        self.after(100, self.process_queue)
        self.after(200, self.auto_detect_gpu_badge)

    def apply_theme(self):
        """Configure modern dark theme styling."""
        self.bg = "#181825"
        self.card_bg = "#1e1e2e"
        self.card_border = "#313244"
        self.fg = "#cdd6f4"
        self.fg_muted = "#a6adc8"
        self.accent = "#89b4fa"
        self.accent_hover = "#b4befe"
        self.success = "#a6e3a1"
        self.error = "#f38ba8"

        self.configure(bg=self.bg)

        style = ttk.Style(self)
        style.theme_use("clam")

        # Custom ttk styles
        style.configure(".", background=self.bg, foreground=self.fg, font=("Segoe UI", 9))
        style.configure("Card.TFrame", background=self.card_bg)

        style.configure("Title.TLabel", background=self.bg, foreground="#ffffff", font=("Segoe UI", 16, "bold"))
        style.configure("Subtitle.TLabel", background=self.bg, foreground=self.fg_muted, font=("Segoe UI", 9))

        style.configure("Section.TLabel", background=self.card_bg, foreground=self.accent, font=("Segoe UI", 10, "bold"))
        style.configure("Card.TLabel", background=self.card_bg, foreground=self.fg, font=("Segoe UI", 9))
        style.configure("CardMuted.TLabel", background=self.card_bg, foreground=self.fg_muted, font=("Segoe UI", 8))

        # Buttons
        style.configure(
            "Primary.TButton",
            background=self.accent,
            foreground="#11111b",
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
            padding=(14, 7),
        )
        style.map("Primary.TButton", background=[("active", self.accent_hover), ("disabled", "#45475a")])

        style.configure(
            "Secondary.TButton",
            background="#313244",
            foreground=self.fg,
            font=("Segoe UI", 9),
            borderwidth=0,
            padding=(10, 5),
        )
        style.map("Secondary.TButton", background=[("active", "#45475a"), ("disabled", "#25263a")])

        style.configure(
            "Danger.TButton",
            background="#45475a",
            foreground=self.error,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
            padding=(10, 5),
        )
        style.map("Danger.TButton", background=[("active", "#585b70"), ("disabled", "#25263a")])

        # Progressbar
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor="#313244",
            background=self.accent,
            lightcolor=self.accent,
            darkcolor=self.accent,
            bordercolor="#313244",
            thickness=14,
        )

        # Radio & Combobox
        style.configure("Card.TRadiobutton", background=self.card_bg, foreground=self.fg, font=("Segoe UI", 9))
        style.map("Card.TRadiobutton", foreground=[("active", self.accent)])

        style.configure(
            "TCombobox",
            fieldbackground="#25263a",
            background="#313244",
            foreground=self.fg,
            arrowcolor=self.accent,
            borderwidth=0,
        )

        # Treeview
        style.configure(
            "Treeview",
            background="#25263a",
            foreground=self.fg,
            fieldbackground="#25263a",
            borderwidth=0,
            rowheight=24,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#313244",
            foreground=self.accent,
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", "#45475a")])

    def build_ui(self):
        # Main scrollable canvas container
        main_frame = tk.Frame(self, bg=self.bg)
        main_frame.pack(fill="both", expand=True, padx=20, pady=16)

        # Header Banner
        header = tk.Frame(main_frame, bg=self.bg)
        header.pack(fill="x", pady=(0, 12))

        title_lbl = ttk.Label(header, text="🎬 FPS Converter", style="Title.TLabel")
        title_lbl.pack(side="left")

        self.gpu_badge_lbl = ttk.Label(header, text="Detecting GPU...", style="Subtitle.TLabel")
        self.gpu_badge_lbl.pack(side="right", pady=4)

        # Card 1: Video Files Selection
        self.build_files_card(main_frame)

        # Card 2: Settings (FPS, GPU, Mode, Output)
        self.build_settings_card(main_frame)

        # Card 3: Progress & Controls
        self.build_progress_card(main_frame)

        # Card 4: Activity Log Console
        self.build_log_card(main_frame)

    def build_files_card(self, parent):
        card = tk.Frame(parent, bg=self.card_bg, highlightbackground=self.card_border, highlightthickness=1)
        card.pack(fill="x", pady=(0, 10), ipady=6, padx=0)

        header_bar = tk.Frame(card, bg=self.card_bg)
        header_bar.pack(fill="x", padx=14, pady=(8, 6))

        ttk.Label(header_bar, text="📁 Input Videos", style="Section.TLabel").pack(side="left")

        btn_box = tk.Frame(header_bar, bg=self.card_bg)
        btn_box.pack(side="right")

        ttk.Button(btn_box, text="+ Browse Video(s)...", style="Primary.TButton", command=self.on_browse_files).pack(side="left", padx=(0, 6))
        ttk.Button(btn_box, text="Remove Selected", style="Secondary.TButton", command=self.on_remove_selected).pack(side="left", padx=(0, 6))
        ttk.Button(btn_box, text="Clear All", style="Secondary.TButton", command=self.on_clear_files).pack(side="left")

        # Treeview table
        tree_frame = tk.Frame(card, bg=self.card_bg)
        tree_frame.pack(fill="x", padx=14, pady=(4, 8))

        columns = ("name", "info", "duration", "size", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=4, selectmode="extended")
        self.tree.heading("name", text="File Name")
        self.tree.heading("info", text="Current Specs")
        self.tree.heading("duration", text="Duration")
        self.tree.heading("size", text="File Size")
        self.tree.heading("status", text="Status")

        self.tree.column("name", width=260, anchor="w")
        self.tree.column("info", width=140, anchor="center")
        self.tree.column("duration", width=80, anchor="center")
        self.tree.column("size", width=80, anchor="center")
        self.tree.column("status", width=120, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")

    def build_settings_card(self, parent):
        card = tk.Frame(parent, bg=self.card_bg, highlightbackground=self.card_border, highlightthickness=1)
        card.pack(fill="x", pady=(0, 10), ipady=8, padx=0)

        header_bar = tk.Frame(card, bg=self.card_bg)
        header_bar.pack(fill="x", padx=14, pady=(8, 8))
        ttk.Label(header_bar, text="⚙️ Conversion Settings", style="Section.TLabel").pack(side="left")

        grid_frame = tk.Frame(card, bg=self.card_bg)
        grid_frame.pack(fill="x", padx=14, pady=4)
        grid_frame.columnconfigure(1, weight=1)
        grid_frame.columnconfigure(3, weight=1)

        # Row 0: Target FPS
        ttk.Label(grid_frame, text="Target FPS:", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=6)

        fps_box = tk.Frame(grid_frame, bg=self.card_bg)
        fps_box.grid(row=0, column=1, sticky="w", pady=6, padx=(8, 20))

        self.fps_var = tk.StringVar(value="60")
        for val in ["24", "30", "60", "120", "144"]:
            btn = tk.Button(
                fps_box,
                text=val,
                font=("Segoe UI", 8, "bold"),
                bg="#313244",
                fg=self.fg,
                activebackground=self.accent,
                activeforeground="#11111b",
                relief="flat",
                padx=8,
                pady=2,
                command=lambda v=val: self.fps_var.set(v),
            )
            btn.pack(side="left", padx=2)

        self.fps_entry = tk.Entry(
            fps_box,
            textvariable=self.fps_var,
            width=5,
            bg="#25263a",
            fg=self.fg,
            insertbackground=self.fg,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            justify="center",
        )
        self.fps_entry.pack(side="left", padx=(6, 0))

        # Row 0: Mode
        ttk.Label(grid_frame, text="Mode:", style="Card.TLabel").grid(row=0, column=2, sticky="w", pady=6)
        mode_box = tk.Frame(grid_frame, bg=self.card_bg)
        mode_box.grid(row=0, column=3, sticky="w", pady=6, padx=(8, 0))

        self.mode_var = tk.StringVar(value="interpolate")
        ttk.Radiobutton(mode_box, text="Duplicate (Fast)", value="duplicate", variable=self.mode_var, command=self.update_mode_hint, style="Card.TRadiobutton").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(mode_box, text="Interpolate (Smooth)", value="interpolate", variable=self.mode_var, command=self.update_mode_hint, style="Card.TRadiobutton").pack(side="left")

        # Mode description hint
        self.mode_hint_lbl = ttk.Label(
            card,
            text="ℹ️ Duplicate mode: Repeats existing frames. To get real buttery-smooth motion, select 'Interpolate (Smooth)'.",
            style="CardMuted.TLabel",
        )
        self.mode_hint_lbl.pack(fill="x", padx=14, pady=(2, 6))
        self.update_mode_hint()

        # Row 1: GPU Backend
        ttk.Label(grid_frame, text="GPU Encoder:", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        gpu_box = tk.Frame(grid_frame, bg=self.card_bg)
        gpu_box.grid(row=1, column=1, sticky="w", pady=6, padx=(8, 20))

        self.gpu_var = tk.StringVar(value="auto")
        self.gpu_combo = ttk.Combobox(
            gpu_box,
            textvariable=self.gpu_var,
            values=["auto", "nvenc", "qsv", "amf", "cpu"],
            state="readonly",
            width=10,
        )
        self.gpu_combo.pack(side="left")

        self.test_gpu_btn = ttk.Button(gpu_box, text="Test Hardware", style="Secondary.TButton", command=self.on_test_hardware)
        self.test_gpu_btn.pack(side="left", padx=(8, 0))

        # Row 1: Output Container
        ttk.Label(grid_frame, text="Container:", style="Card.TLabel").grid(row=1, column=2, sticky="w", pady=6)
        ext_box = tk.Frame(grid_frame, bg=self.card_bg)
        ext_box.grid(row=1, column=3, sticky="w", pady=6, padx=(8, 0))

        self.ext_var = tk.StringVar(value=".mp4")
        self.ext_combo = ttk.Combobox(
            ext_box,
            textvariable=self.ext_var,
            values=[".mp4", ".mkv", ".mov"],
            state="readonly",
            width=8,
        )
        self.ext_combo.pack(side="left")

        # Row 2: Output Directory
        ttk.Label(grid_frame, text="Output Folder:", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=6)

        out_box = tk.Frame(grid_frame, bg=self.card_bg)
        out_box.grid(row=2, column=1, columnspan=3, sticky="ew", pady=6, padx=(8, 0))

        default_out = Path("converted").resolve()
        self.outdir_var = tk.StringVar(value=str(default_out))

        self.outdir_entry = tk.Entry(
            out_box,
            textvariable=self.outdir_var,
            bg="#25263a",
            fg=self.fg,
            insertbackground=self.fg,
            relief="flat",
            font=("Segoe UI", 9),
        )
        self.outdir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Button(out_box, text="Browse Folder...", style="Secondary.TButton", command=self.on_browse_output).pack(side="left")

    def build_progress_card(self, parent):
        card = tk.Frame(parent, bg=self.card_bg, highlightbackground=self.card_border, highlightthickness=1)
        card.pack(fill="x", pady=(0, 10), ipady=8, padx=0)

        header_bar = tk.Frame(card, bg=self.card_bg)
        header_bar.pack(fill="x", padx=14, pady=(8, 4))

        self.status_lbl = ttk.Label(header_bar, text="Ready to convert", style="Section.TLabel")
        self.status_lbl.pack(side="left")

        self.stats_lbl = ttk.Label(header_bar, text="", style="CardMuted.TLabel")
        self.stats_lbl.pack(side="right")

        # Progress bar
        prog_frame = tk.Frame(card, bg=self.card_bg)
        prog_frame.pack(fill="x", padx=14, pady=6)

        self.prog_var = tk.DoubleVar(value=0.0)
        self.progressbar = ttk.Progressbar(
            prog_frame,
            variable=self.prog_var,
            maximum=100.0,
            style="Accent.Horizontal.TProgressbar",
        )
        self.progressbar.pack(fill="x", expand=True)

        # Action Buttons bar
        act_bar = tk.Frame(card, bg=self.card_bg)
        act_bar.pack(fill="x", padx=14, pady=(6, 4))

        self.start_btn = ttk.Button(act_bar, text="▶ Start Conversion", style="Primary.TButton", command=self.on_start_conversion)
        self.start_btn.pack(side="left", padx=(0, 8))

        self.cancel_btn = ttk.Button(act_bar, text="■ Cancel", style="Danger.TButton", state="disabled", command=self.on_cancel_conversion)
        self.cancel_btn.pack(side="left", padx=(0, 8))

        self.open_folder_btn = ttk.Button(act_bar, text="📂 Open Output Folder", style="Secondary.TButton", command=self.on_open_folder)
        self.open_folder_btn.pack(side="right")

    def build_log_card(self, parent):
        card = tk.Frame(parent, bg=self.card_bg, highlightbackground=self.card_border, highlightthickness=1)
        card.pack(fill="both", expand=True, pady=(0, 0), ipady=4, padx=0)

        header_bar = tk.Frame(card, bg=self.card_bg)
        header_bar.pack(fill="x", padx=14, pady=(6, 4))
        ttk.Label(header_bar, text="📋 Activity Log", style="Section.TLabel").pack(side="left")

        log_frame = tk.Frame(card, bg=self.card_bg)
        log_frame.pack(fill="both", expand=True, padx=14, pady=(2, 8))

        self.log_text = tk.Text(
            log_frame,
            bg="#11111b",
            fg=self.fg,
            insertbackground=self.fg,
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
            height=6,
        )
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    # ----------------------------------------------------
    # Logging and status helpers
    # ----------------------------------------------------
    def update_mode_hint(self):
        """Update helper hint based on selected conversion mode."""
        if self.mode_var.get() == "interpolate":
            self.mode_hint_lbl.config(
                text="✨ Interpolate mode: Synthesizes brand-new in-between frames for real silky-smooth motion (computationally heavy, runs on CPU).",
                foreground=self.accent,
            )
        else:
            self.mode_hint_lbl.config(
                text="ℹ️ Duplicate mode: Repeats existing frames. Fast, but motion will look identical to original.",
                foreground=self.fg_muted,
            )

    def log(self, text: str):
        """Append line to activity log window."""
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {text}\n")
        self.log_text.see("end")

    def auto_detect_gpu_badge(self):
        """Probe available GPU silently on startup."""
        def run_detect():
            try:
                b = fps_converter.pick_backend("auto")
                enc = fps_converter.BACKENDS[b]["encoder"]
                self.msg_queue.put(("badge", f"Hardware: {b.upper()} ({enc})"))
                self.msg_queue.put(("log", f"Detected GPU encoder: {enc} ({b.upper()})"))
            except Exception as e:
                self.msg_queue.put(("badge", "Hardware: CPU (libx264)"))
                self.msg_queue.put(("log", f"Hardware probe fallback to CPU: {e}"))

        threading.Thread(target=run_detect, daemon=True).start()

    def on_test_hardware(self):
        """Manual test hardware button."""
        self.test_gpu_btn.config(state="disabled")
        self.log("Testing hardware encoders (NVENC / QSV / AMF / CPU)...")

        def run_test():
            pref = self.gpu_var.get()
            try:
                b = fps_converter.pick_backend(pref)
                enc = fps_converter.BACKENDS[b]["encoder"]
                msg = f"Backend '{b}' is active and operational! ({enc})"
                self.msg_queue.put(("log", msg))
                self.msg_queue.put(("badge", f"Hardware: {b.upper()} ({enc})"))
                self.msg_queue.put(("info_box", ("Hardware Test Succeeded", msg)))
            except Exception as e:
                self.msg_queue.put(("log", f"Backend error: {e}"))
                self.msg_queue.put(("error_box", ("Hardware Test Failed", str(e))))
            finally:
                self.msg_queue.put(("btn_enable", self.test_gpu_btn))

        threading.Thread(target=run_test, daemon=True).start()

    # ----------------------------------------------------
    # File Management
    # ----------------------------------------------------
    def on_browse_files(self):
        files = filedialog.askopenfilenames(
            title="Select Video Files to Convert",
            filetypes=[
                ("Video Files", "*.mp4;*.mkv;*.mov;*.webm;*.avi;*.flv;*.ts;*.wmv;*.m4v"),
                ("MP4 Files", "*.mp4"),
                ("MKV Files", "*.mkv"),
                ("MOV Files", "*.mov"),
                ("All Files", "*.*"),
            ],
        )
        if not files:
            return

        for f in files:
            p = Path(f)
            if p not in self.selected_files:
                self.selected_files.append(p)
                self.add_file_to_tree(p)

        self.log(f"Added {len(files)} file(s). Total: {len(self.selected_files)}")

    def add_file_to_tree(self, p: Path):
        """Probe file in thread and add row to Treeview."""
        file_size_mb = f"{p.stat().st_size / (1024 * 1024):.1f} MB" if p.is_file() else "N/A"
        item_id = self.tree.insert("", "end", values=(p.name, "Probing...", "...", file_size_mb, "Ready"))

        def probe_file():
            try:
                info = fps_converter.probe(p)
                if not fps_converter.has_video(info):
                    self.msg_queue.put(("tree_update", (item_id, p.name, "Audio-Only", "--:--", file_size_mb, "Skipped (No Video)")))
                    return

                dur_sec = fps_converter.get_video_duration(info)
                dur_str = time.strftime("%H:%M:%S", time.gmtime(dur_sec)) if dur_sec > 0 else "Unknown"

                # Extract res & fps
                spec = "Video"
                for s in info.get("streams", []):
                    if s.get("codec_type") == "video":
                        w = s.get("width", "?")
                        h = s.get("height", "?")
                        rate_str = s.get("r_frame_rate", "")
                        fps_val = ""
                        if "/" in rate_str:
                            try:
                                num, den = map(int, rate_str.split("/"))
                                if den > 0:
                                    fps_val = f" @ {round(num / den)}fps"
                            except Exception:
                                pass
                        spec = f"{w}x{h}{fps_val}"
                        break

                self.msg_queue.put(("tree_update", (item_id, p.name, spec, dur_str, file_size_mb, "Ready")))
            except Exception:
                self.msg_queue.put(("tree_update", (item_id, p.name, "Unreadable", "--:--", file_size_mb, "Error")))

        threading.Thread(target=probe_file, daemon=True).start()

    def on_remove_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            return
        for item in selected_items:
            vals = self.tree.item(item, "values")
            name = vals[0]
            self.selected_files = [f for f in self.selected_files if f.name != name]
            self.tree.delete(item)

    def on_clear_files(self):
        self.selected_files.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.prog_var.set(0)
        self.status_lbl.config(text="Ready to convert", foreground=self.accent)
        self.stats_lbl.config(text="")

    def on_browse_output(self):
        d = filedialog.askdirectory(title="Select Output Folder")
        if d:
            self.outdir_var.set(d)

    def on_open_folder(self):
        folder = Path(self.outdir_var.get()).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])

    # ----------------------------------------------------
    # Conversion Process
    # ----------------------------------------------------
    def on_start_conversion(self):
        if not self.selected_files:
            messagebox.showwarning("No Input Files", "Please browse and select at least one video file.")
            return

        try:
            target_fps = float(self.fps_var.get().strip())
            if target_fps <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Invalid FPS", "Target FPS must be a positive number (e.g., 60, 30, 24).")
            return

        outdir = Path(self.outdir_var.get().strip()).resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        backend_choice = self.gpu_var.get()
        mode_choice = self.mode_var.get()
        ext_choice = self.ext_var.get()

        self.is_converting = True
        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.prog_var.set(0)
        self.status_lbl.config(text="Initializing conversion...", foreground=self.accent)

        def worker():
            try:
                backend = fps_converter.pick_backend(backend_choice)
                enc_name = fps_converter.BACKENDS[backend]["encoder"]
                self.msg_queue.put(("log", f"Starting batch | Target: {target_fps:g} FPS | Backend: {enc_name} | Mode: {mode_choice}"))

                total_files = len(self.selected_files)
                failed_files = []

                for idx, src in enumerate(self.selected_files, 1):
                    if self.stop_event.is_set():
                        self.msg_queue.put(("log", "Batch halted by user."))
                        break

                    self.msg_queue.put(("set_tree_status", (src.name, "Converting...")))
                    dst = outdir / f"{src.stem}_{target_fps:g}fps{ext_choice}"

                    self.msg_queue.put(("status", f"Converting [{idx}/{total_files}]: {src.name}"))
                    self.msg_queue.put(("log", f"[{idx}/{total_files}] Converting: {src.name} -> {dst.name}"))

                    start_time = time.time()

                    def progress_cb(pct, speed, fps_val, cur_sec, dur_sec):
                        time_str = f"{time.strftime('%M:%S', time.gmtime(cur_sec))} / {time.strftime('%M:%S', time.gmtime(dur_sec))}" if dur_sec > 0 else ""
                        self.msg_queue.put(("progress", (pct, f"{pct:.1f}% | Speed: {speed} | FPS: {fps_val:.0f} | {time_str}")))

                    try:
                        fps_converter.convert(
                            src,
                            dst,
                            target_fps,
                            backend,
                            mode_choice,
                            progress_callback=progress_cb,
                            stop_event=self.stop_event,
                        )
                        elapsed = time.time() - start_time
                        self.msg_queue.put(("set_tree_status", (src.name, "Done")))
                        self.msg_queue.put(("log", f"✓ Done: {dst.name} in {elapsed:.1f}s"))
                    except fps_converter.AudioOnlyError as e:
                        self.msg_queue.put(("set_tree_status", (src.name, "Skipped (No Video)")))
                        self.msg_queue.put(("log", f"⚠ Skipped: {src.name} ({e})"))
                    except Exception as e:
                        if self.stop_event.is_set():
                            self.msg_queue.put(("set_tree_status", (src.name, "Cancelled")))
                            self.msg_queue.put(("log", f"⏹ Cancelled: {src.name}"))
                            break
                        failed_files.append(src.name)
                        self.msg_queue.put(("set_tree_status", (src.name, "Failed")))
                        self.msg_queue.put(("log", f"✗ Failed: {src.name}: {e}"))

                # Batch summary
                if self.stop_event.is_set():
                    self.msg_queue.put(("status_done", ("Conversion cancelled.", self.error)))
                elif failed_files:
                    self.msg_queue.put(("status_done", (f"Completed with {len(failed_files)} failure(s).", self.error)))
                else:
                    self.msg_queue.put(("status_done", (f"All {total_files} file(s) converted successfully!", self.success)))

            except Exception as e:
                self.msg_queue.put(("log", f"Fatal error: {e}"))
                self.msg_queue.put(("status_done", (f"Error: {e}", self.error)))
            finally:
                self.msg_queue.put(("conversion_finished", None))

        threading.Thread(target=worker, daemon=True).start()

    def on_cancel_conversion(self):
        if self.is_converting:
            self.stop_event.set()
            self.cancel_btn.config(state="disabled")
            self.status_lbl.config(text="Cancelling conversion...", foreground=self.error)
            self.log("Stopping ongoing conversion...")

    # ----------------------------------------------------
    # Queue Handler for GUI Thread Safety
    # ----------------------------------------------------
    def process_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()

                if msg_type == "log":
                    self.log(data)
                elif msg_type == "status":
                    self.status_lbl.config(text=data, foreground=self.accent)
                elif msg_type == "progress":
                    pct, stats = data
                    self.prog_var.set(pct)
                    self.stats_lbl.config(text=stats)
                elif msg_type == "status_done":
                    text, color = data
                    self.status_lbl.config(text=text, foreground=color)
                    self.stats_lbl.config(text="")
                    self.prog_var.set(100.0)
                elif msg_type == "badge":
                    self.gpu_badge_lbl.config(text=data)
                elif msg_type == "btn_enable":
                    data.config(state="normal")
                elif msg_type == "tree_update":
                    item_id, name, info, dur, sz, st = data
                    if self.tree.exists(item_id):
                        self.tree.item(item_id, values=(name, info, dur, sz, st))
                elif msg_type == "set_tree_status":
                    name, new_status = data
                    for item in self.tree.get_children():
                        vals = self.tree.item(item, "values")
                        if vals and vals[0] == name:
                            self.tree.item(item, values=(vals[0], vals[1], vals[2], vals[3], new_status))
                            break
                elif msg_type == "conversion_finished":
                    self.is_converting = False
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                elif msg_type == "info_box":
                    title, msg = data
                    messagebox.showinfo(title, msg)
                elif msg_type == "error_box":
                    title, msg = data
                    messagebox.showerror(title, msg)

        except queue.Empty:
            pass

        self.after(50, self.process_queue)


def run_gui():
    """Launch the FPS Converter graphical interface."""
    app = FpsConverterGUI()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
