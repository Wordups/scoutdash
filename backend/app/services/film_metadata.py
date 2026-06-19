"""Video metadata and frame extraction backed by static FFmpeg binaries."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any


_PATHS_READY = False


def ensure_binaries() -> tuple[str, str]:
    """Make FFmpeg and FFprobe available and return their absolute paths."""
    global _PATHS_READY
    if not _PATHS_READY:
        try:
            import static_ffmpeg

            static_ffmpeg.add_paths()
        except ImportError as exc:
            raise RuntimeError(
                "static-ffmpeg not installed. Run: pip install static-ffmpeg"
            ) from exc
        _PATHS_READY = True

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError(
            f"binary resolution failed (ffmpeg={ffmpeg}, ffprobe={ffprobe})"
        )
    return ffmpeg, ffprobe


def probe(path: str) -> dict[str, Any]:
    """Return normalized film metadata from FFprobe."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"source file not found: {path}")

    _, ffprobe = ensure_binaries()
    command = [
        ffprobe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "-i",
        path,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"ffprobe could not inspect the film: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    container = data.get("format", {})
    container_tags = container.get("tags", {})
    video = next(
        (stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"),
        {},
    )
    if not video:
        raise RuntimeError("ffprobe did not find a video stream")
    video_tags = video.get("tags", {})

    duration = _to_float(container.get("duration")) or _to_float(video.get("duration"))
    fps = _parse_rate(video.get("avg_frame_rate")) or _parse_rate(video.get("r_frame_rate"))
    frame_count = _to_int(video.get("nb_frames"))
    if not frame_count and duration and fps:
        frame_count = round(duration * fps)

    return {
        "filename": os.path.basename(path),
        "format": container.get("format_name"),
        "duration_seconds": round(duration, 3) if duration is not None else None,
        "fps": fps,
        "frame_count": frame_count,
        "width": video.get("width"),
        "height": video.get("height"),
        "codec": video.get("codec_name"),
        "pixel_format": video.get("pix_fmt"),
        "bitrate": _to_int(container.get("bit_rate")),
        "creation_time": container_tags.get("creation_time") or video_tags.get("creation_time"),
        "location": container_tags.get("location"),
    }


def extract_frames(
    path: str,
    out_dir: str,
    interval_seconds: float = 3.0,
    quality: int = 2,
) -> list[dict[str, Any]]:
    """Extract one review frame at each interval. Run this in background work."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"source file not found: {path}")
    os.makedirs(out_dir, exist_ok=True)

    ffmpeg, _ = ensure_binaries()
    pattern = os.path.join(out_dir, "frame_%05d.jpg")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        path,
        "-vf",
        f"fps=1/{interval_seconds}",
        "-q:v",
        str(quality),
        "-f",
        "image2",
        pattern,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(f"frame extraction failed: {result.stderr.strip()}")

    frames = sorted(name for name in os.listdir(out_dir) if name.startswith("frame_"))
    return [
        {
            "index": index + 1,
            "timestamp": round(index * interval_seconds, 3),
            "path": os.path.join(out_dir, name),
        }
        for index, name in enumerate(frames)
    ]


def extract_frame_at(path: str, timestamp: float, out_path: str, quality: int = 2) -> str:
    """Extract one frame at an exact film timestamp."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"source file not found: {path}")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    ffmpeg, _ = ensure_binaries()
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(timestamp),
        "-i",
        path,
        "-frames:v",
        "1",
        "-q:v",
        str(quality),
        "-y",
        out_path,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"ffprobe could not inspect the film: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(f"frame grab failed: {result.stderr.strip()}")
    return out_path


def capabilities() -> dict[str, str | bool | None]:
    """Invoke both binaries and return an honest processing readiness signal."""
    result: dict[str, str | bool | None] = {
        "ffmpeg": None,
        "ffprobe": None,
        "ready": False,
        "error": None,
    }
    try:
        ffmpeg, ffprobe = ensure_binaries()
        result["ffmpeg"] = ffmpeg
        result["ffprobe"] = ffprobe
        subprocess.run([ffmpeg, "-version"], capture_output=True, check=True, timeout=30)
        subprocess.run([ffprobe, "-version"], capture_output=True, check=True, timeout=30)
        result["ready"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    return result


def _parse_rate(rate: str | None) -> float | None:
    if not rate or rate == "0/0":
        return None
    try:
        numerator, denominator = rate.split("/")
        denominator_value = float(denominator)
        return round(float(numerator) / denominator_value, 3) if denominator_value else None
    except (ValueError, ZeroDivisionError):
        return None


def _to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
