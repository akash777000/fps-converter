#!/usr/bin/env python3
"""
fps_converter.py - convert any video to a target FPS, using GPU encoding when possible.

Examples:
  python fps_converter.py clip.mkv
  python fps_converter.py *.mp4 --fps 60 --gpu nvenc
  python fps_converter.py movie.mov --fps 120 --mode interpolate -o out
  python fps_converter.py --gui
"""
import argparse
import glob
import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path


class AudioOnlyError(RuntimeError):
    """Raised when an input file contains no real video streams."""
    pass


# Each GPU backend: encoder name, optional hardware decode, and quality settings
BACKENDS = {
    "nvenc": {
        "encoder": "h264_nvenc",
        "hwaccel": ["-hwaccel", "cuda"],
        "quality": ["-preset", "p5", "-cq", "23"],
    },
    "qsv": {
        "encoder": "h264_qsv",
        "hwaccel": ["-hwaccel", "qsv"],
        "quality": ["-global_quality", "23"],
    },
    "amf": {  # AMD: encode on GPU, decode on CPU (simplest and most portable)
        "encoder": "h264_amf",
        "hwaccel": [],
        "quality": ["-quality", "balanced", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23"],
    },
    "cpu": {
        "encoder": "libx264",
        "hwaccel": [],
        "quality": ["-preset", "medium", "-crf", "20"],
    },
}


def probe(path: Path) -> dict:
    """Run ffprobe on path and return parsed JSON metadata."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "ffprobe failed")
    return json.loads(r.stdout)


def has_video(info: dict) -> bool:
    """Check if metadata contains at least one non-attached video stream."""
    return any(
        s.get("codec_type") == "video"
        and not s.get("disposition", {}).get("attached_pic", 0)
        for s in info.get("streams", [])
    )


def get_video_duration(info: dict) -> float:
    """Extract total video duration in seconds from format or video stream."""
    fmt = info.get("format", {})
    if "duration" in fmt:
        try:
            val = float(fmt["duration"])
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass
    for s in info.get("streams", []):
        if s.get("codec_type") == "video" and "duration" in s:
            try:
                val = float(s["duration"])
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass
    return 0.0


def pick_backend(preferred: str) -> str:
    """Actually test each encoder with a tiny encode. Listing an encoder isn't enough;
    the GPU or driver has to really work."""
    order = ["nvenc", "qsv", "amf", "cpu"] if preferred == "auto" else [preferred]
    for name in order:
        test = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2",
             "-frames:v", "1", "-c:v", BACKENDS[name]["encoder"],
             "-f", "null", "-"],
            capture_output=True,
        )
        if test.returncode == 0:
            return name
    if preferred != "auto":
        raise RuntimeError(f"Requested GPU '{preferred}' isn't available on this machine.")
    return "cpu"


def convert(
    src: Path,
    dst: Path,
    fps: float,
    backend: str,
    mode: str,
    progress_callback=None,
    stop_event: threading.Event = None,
) -> None:
    """Convert a video file to target FPS with optional progress callback."""
    info = probe(src)
    if not has_video(info):
        raise AudioOnlyError("no video stream (audio-only file)")

    duration = get_video_duration(info)
    cfg = BACKENDS[backend]

    if mode == "interpolate":
        # Generates in-between frames for smoother motion. This filter runs on the CPU
        # only, so the GPU helps with decode and encode, not this step. It's slow.
        vf = f"minterpolate=fps={fps}:mi_mode=mci"
    else:
        # Fast: repeats or drops frames to hit the target rate
        vf = f"fps={fps}"

    # Apply faststart only for MP4/MOV container types
    mov_flags = ["-movflags", "+faststart"] if dst.suffix.lower() in {".mp4", ".mov", ".m4v"} else []

    cmd = [
        "ffmpeg", "-hide_banner", "-y",
        *cfg["hwaccel"],
        "-i", str(src),
        "-map", "0:v:0",           # first video stream
        "-map", "0:a?",            # all audio, if any
        "-vf", vf,
        "-c:v", cfg["encoder"], *cfg["quality"],
        "-pix_fmt", "yuv420p",     # plays on basically every device
        "-c:a", "aac", "-b:a", "192k",  # re-encode audio so any container works
        *mov_flags,
    ]

    if progress_callback is None:
        cmd.append(str(dst))
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError("ffmpeg failed (see output above)")
        return

    # Progress tracking mode
    cmd.extend(["-progress", "pipe:1", "-nostats", str(dst)])
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    current_speed = "N/A"
    current_fps = 0.0

    if proc.stdout:
        for line in proc.stdout:
            if stop_event and stop_event.is_set():
                proc.terminate()
                raise RuntimeError("Conversion cancelled by user")

            line = line.strip()
            if not line:
                continue

            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k == "out_time_us":
                    try:
                        us = int(v)
                        sec = us / 1_000_000.0
                        pct = (sec / duration * 100.0) if duration > 0 else 0.0
                        progress_callback(min(100.0, max(0.0, pct)), current_speed, current_fps, sec, duration)
                    except ValueError:
                        pass
                elif k == "speed":
                    current_speed = v
                elif k == "fps":
                    try:
                        current_fps = float(v)
                    except ValueError:
                        pass
                elif k == "progress" and v == "end":
                    progress_callback(100.0, current_speed, current_fps, duration, duration)

    proc.wait()
    if stop_event and stop_event.is_set():
        raise RuntimeError("Conversion cancelled by user")

    if proc.returncode != 0:
        err_msg = proc.stderr.read().strip() if proc.stderr else "ffmpeg failed"
        raise RuntimeError(err_msg or "ffmpeg failed")


def expand_wildcards(patterns: list[Path]) -> list[Path]:
    """Expand wildcard paths (useful on Windows where the shell doesn't expand them)."""
    expanded: list[Path] = []
    for p in patterns:
        p_str = str(p)
        if any(c in p_str for c in ("*", "?")):
            matched = glob.glob(p_str)
            if matched:
                expanded.extend(Path(m) for m in matched)
            else:
                expanded.append(p)
        else:
            expanded.append(p)
    return expanded


def main() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("ffmpeg/ffprobe not found. Install FFmpeg and make sure it's on PATH.")

    # If run with no CLI arguments or with --gui, open the graphical UI
    if len(sys.argv) == 1 or "--gui" in sys.argv:
        try:
            import gui
            gui.run_gui()
            return
        except ImportError:
            pass

    p = argparse.ArgumentParser(description="Convert videos to a target FPS, using the GPU.")
    p.add_argument("inputs", nargs="*", type=Path, help="Input files (any container)")
    p.add_argument("--fps", type=float, default=60, help="Target frame rate (default: 60)")
    p.add_argument("--gpu", choices=["auto", "nvenc", "qsv", "amf", "cpu"], default="auto",
                   help="Encoder backend (default: auto-detect)")
    p.add_argument("--mode", choices=["duplicate", "interpolate"], default="interpolate",
                   help="interpolate = smoother motion (default, slow); duplicate = fast frame repeat")
    p.add_argument("-o", "--outdir", type=Path, default=Path("converted"))
    p.add_argument("--ext", default=".mp4", help="Output container, e.g. .mp4, .mkv, .mov")
    p.add_argument("--gui", action="store_true", help="Launch GUI interface")
    args = p.parse_args()

    if args.gui or not args.inputs:
        import gui
        gui.run_gui()
        return

    backend = pick_backend(args.gpu)
    print(f"Using encoder: {BACKENDS[backend]['encoder']}  |  target: {args.fps:g} fps\n")
    args.outdir.mkdir(parents=True, exist_ok=True)

    ext = args.ext if args.ext.startswith(".") else f".{args.ext}"
    input_files = expand_wildcards(args.inputs)

    failed = []
    for src in input_files:
        if not src.is_file():
            print(f"[skip] {src}: not a file")
            failed.append(src)
            continue
        dst = args.outdir / f"{src.stem}_{args.fps:g}fps{ext}"
        print(f"[convert] {src} -> {dst}")
        try:
            convert(src, dst, args.fps, backend, args.mode)
            print(f"[done]    {dst}\n")
        except AudioOnlyError as e:
            print(f"[skip]    {src}: {e}\n")
            failed.append(src)
        except RuntimeError as e:
            print(f"[fail]    {src}: {e}\n")
            failed.append(src)

    if failed:
        sys.exit(f"{len(failed)} file(s) failed.")


if __name__ == "__main__":
    main()
