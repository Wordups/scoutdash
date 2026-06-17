from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class ExtractedFrame:
    frame_number: int
    timestamp_seconds: float
    path: Path
    width: int | None
    height: int | None


def probe_video(path: Path) -> dict[str, float | int | None]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=duration,avg_frame_rate,nb_frames",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, check=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"duration_seconds": None, "fps": None, "frame_count": None}

    payload = json.loads(completed.stdout or "{}")
    stream = (payload.get("streams") or [{}])[0]
    duration = _float_or_none(stream.get("duration"))
    fps = _parse_rate(stream.get("avg_frame_rate"))
    frame_count = _int_or_none(stream.get("nb_frames"))
    return {"duration_seconds": duration, "fps": fps, "frame_count": frame_count}


def extract_sampled_frames(
    video_path: Path,
    output_dir: Path,
    sample_fps: float = 1.0,
    max_frames: int = 240,
) -> list[ExtractedFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame_%06d.jpg"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={sample_fps},scale=640:-1",
        "-frames:v",
        str(max_frames),
        "-q:v",
        "2",
        str(pattern),
    ]
    subprocess.run(command, capture_output=True, check=True, text=True, timeout=120)

    frames: list[ExtractedFrame] = []
    for index, path in enumerate(sorted(output_dir.glob("frame_*.jpg"))):
        width: int | None = None
        height: int | None = None
        try:
            with Image.open(path) as image:
                width, height = image.size
        except OSError:
            pass
        frames.append(
            ExtractedFrame(
                frame_number=index,
                timestamp_seconds=index / sample_fps,
                path=path,
                width=width,
                height=height,
            )
        )
    return frames


def _parse_rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        numerator, denominator = value.split("/", maxsplit=1)
        den = _float_or_none(denominator)
        if not den:
            return None
        num = _float_or_none(numerator)
        return None if num is None else num / den
    return _float_or_none(value)


def _float_or_none(value: str | float | None) -> float | None:
    try:
        return None if value is None else float(value)
    except ValueError:
        return None


def _int_or_none(value: str | int | None) -> int | None:
    try:
        return None if value is None else int(value)
    except ValueError:
        return None
