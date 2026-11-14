# FPS Converter

Convert videos to a chosen frame rate with a desktop GUI or command line. Choose fast frame duplication, motion-compensated frame interpolation, and an available hardware or CPU encoder.

## Features

- Convert one video or process a batch of files.
- Set a target frame rate and choose an output directory and container.
- Use NVIDIA NVENC, Intel Quick Sync (QSV), AMD AMF, or the CPU encoder (`libx264`).
- Automatically test available encoders and fall back to the CPU when using `--gpu auto`.
- Choose between fast frame duplication/dropping and motion-compensated interpolation.
- Keep audio streams, re-encoding them as AAC at 192 kbps.
- View conversion progress in the GUI and cancel a running conversion.
- Detect audio-only inputs and report files that could not be converted.

The converter supports input formats that your FFmpeg build can read. Hardware encoders must be supported by both FFmpeg and your device/driver.

## Requirements

- Python 3.9 or later.
- FFmpeg and `ffprobe`, both available on your `PATH`.
- Tkinter for the graphical interface (usually included with desktop Python distributions).

No third-party Python packages are required. The `requirements.txt` file is provided for tooling compatibility.

Check that FFmpeg is available:

```shell
ffmpeg -version
ffprobe -version
```

Install FFmpeg using your platform's package manager or a trusted FFmpeg distribution. For example:

```powershell
winget install Gyan.FFmpeg
```

```shell
brew install ffmpeg
```

```shell
sudo apt install ffmpeg
```

## Run

Start the GUI:

```shell
python fps_converter.py
```

You can also run `python gui.py` or `python fps_converter.py --gui`. In the GUI, add videos, choose the frame rate, encoder, conversion mode, and output settings, then start the conversion.

Convert a single video from the command line:

```shell
python fps_converter.py input.mkv --fps 60 --gpu auto --mode interpolate
```

Convert matching files using the CPU encoder and fast frame duplication:

```shell
python fps_converter.py *.mp4 --gpu cpu --mode duplicate -o converted
```

Choose another output container:

```shell
python fps_converter.py input.mov --fps 30 --ext .mkv -o converted
```

## Command-line options

| Option | Default | Description |
| --- | --- | --- |
| `inputs` | None | One or more input paths or wildcard patterns. If omitted, the GUI opens. |
| `--fps` | `60` | Target frame rate. |
| `--gpu` | `auto` | Encoder: `auto`, `nvenc`, `qsv`, `amf`, or `cpu`. |
| `--mode` | `interpolate` | `interpolate` creates in-between frames; `duplicate` repeats or drops frames. |
| `-o`, `--outdir` | `converted` | Destination directory. |
| `--ext` | `.mp4` | Output extension, such as `.mp4`, `.mkv`, or `.mov`. |
| `--gui` | Off | Open the graphical interface. |

Use `python fps_converter.py --help` to see the options in your terminal.

## Conversion modes and performance

- **Duplicate** uses FFmpeg's `fps` filter to repeat or drop frames. It is the faster option, but does not create new motion detail.
- **Interpolate** uses FFmpeg's `minterpolate` filter to synthesize intermediate frames. This can produce smoother motion, but is significantly slower and runs on the CPU, even when GPU encoding is selected.
- **GPU encoding** depends on FFmpeg build support and compatible hardware/drivers. `auto` tests candidate encoders; explicitly selecting an unavailable encoder reports an error. The CPU option works with FFmpeg builds that include `libx264`.

The output uses H.264 video (`yuv420p`) and AAC audio. MP4, MOV, and M4V outputs are written with the `faststart` flag.

## Tests

The test suite creates short media fixtures with FFmpeg, so FFmpeg and `ffprobe` must be installed:

```shell
python -m unittest -v test_fps_converter.py
```
