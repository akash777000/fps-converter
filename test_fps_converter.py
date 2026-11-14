#!/usr/bin/env python3
"""
test_fps_converter.py - Comprehensive test suite for fps_converter.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

import fps_converter


class TestFpsConverter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path("test_fixtures")
        cls.test_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dir = Path("test_output")
        cls.out_dir.mkdir(parents=True, exist_ok=True)

        cls.sample_video = cls.test_dir / "sample_24fps.mp4"
        cls.sample_audio = cls.test_dir / "sample_audio.m4a"

        # Generate a 1-second 24 fps test video with audio
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-c:a", "aac",
            str(cls.sample_video)
        ], check=True)

        # Generate an audio-only file
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:a", "aac",
            str(cls.sample_audio)
        ], check=True)

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        if cls.out_dir.exists():
            shutil.rmtree(cls.out_dir, ignore_errors=True)

    def test_ffmpeg_available(self):
        self.assertIsNotNone(shutil.which("ffmpeg"))
        self.assertIsNotNone(shutil.which("ffprobe"))

    def test_backend_detection(self):
        backend = fps_converter.pick_backend("auto")
        self.assertIn(backend, ["nvenc", "qsv", "amf", "cpu"])
        self.assertIn(backend, fps_converter.BACKENDS)

    def test_probe_and_has_video(self):
        info_vid = fps_converter.probe(self.sample_video)
        self.assertTrue(fps_converter.has_video(info_vid))

        info_aud = fps_converter.probe(self.sample_audio)
        self.assertFalse(fps_converter.has_video(info_aud))

    def test_convert_to_60fps(self):
        dst = self.out_dir / "sample_60fps.mp4"
        backend = fps_converter.pick_backend("auto")
        fps_converter.convert(self.sample_video, dst, 60.0, backend, "duplicate")
        self.assertTrue(dst.is_file())

        # Verify output FPS with ffprobe
        info = fps_converter.probe(dst)
        video_stream = next(s for s in info["streams"] if s.get("codec_type") == "video")
        r_frame_rate = video_stream.get("r_frame_rate")
        num, den = map(int, r_frame_rate.split("/"))
        self.assertEqual(round(num / den), 60)

    def test_interpolate_mode_outputs_target_fps(self):
        dst = self.out_dir / "sample_60fps_interpolated.mp4"
        fps_converter.convert(self.sample_video, dst, 60.0, "cpu", "interpolate")
        self.assertTrue(dst.is_file())

        info = fps_converter.probe(dst)
        video_stream = next(s for s in info["streams"] if s.get("codec_type") == "video")
        avg_frame_rate = video_stream.get("avg_frame_rate")
        num, den = map(int, avg_frame_rate.split("/"))
        self.assertEqual(round(num / den), 60)

    def test_convert_cpu_mode(self):
        dst = self.out_dir / "sample_cpu_30fps.mp4"
        fps_converter.convert(self.sample_video, dst, 30.0, "cpu", "duplicate")
        self.assertTrue(dst.is_file())

        info = fps_converter.probe(dst)
        video_stream = next(s for s in info["streams"] if s.get("codec_type") == "video")
        r_frame_rate = video_stream.get("r_frame_rate")
        num, den = map(int, r_frame_rate.split("/"))
        self.assertEqual(round(num / den), 30)

    def test_convert_mkv_container(self):
        dst = self.out_dir / "sample_60fps.mkv"
        backend = fps_converter.pick_backend("auto")
        fps_converter.convert(self.sample_video, dst, 60.0, backend, "duplicate")
        self.assertTrue(dst.is_file())
        self.assertEqual(dst.suffix, ".mkv")

    def test_audio_only_rejection(self):
        dst = self.out_dir / "audio_out.mp4"
        backend = fps_converter.pick_backend("auto")
        with self.assertRaises(fps_converter.AudioOnlyError):
            fps_converter.convert(self.sample_audio, dst, 60.0, backend, "duplicate")

    def test_cli_execution(self):
        out_cli = self.out_dir / "cli_run"
        res = subprocess.run([
            "python", "fps_converter.py",
            str(self.sample_video),
            "--fps", "48",
            "-o", str(out_cli)
        ], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        expected_out = out_cli / "sample_24fps_48fps.mp4"
        self.assertTrue(expected_out.is_file())


if __name__ == "__main__":
    unittest.main()
