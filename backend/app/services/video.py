from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.core.config import Settings
from app.services.film_metadata import capabilities, ensure_binaries, probe


@dataclass(frozen=True)
class ExtractedFrame:
    frame_number: int
    timestamp_seconds: float
    path: Path
    width: int | None
    height: int | None


class VideoProcessingError(RuntimeError):
    pass


def resolve_ffmpeg(settings: Settings) -> str:
    configured = settings.ffmpeg_binary
    if configured:
        resolved = shutil.which(configured) or (configured if Path(configured).is_file() else None)
        if resolved:
            return str(resolved)
        raise VideoProcessingError(f"Configured FFmpeg binary was not found: {configured}")

    try:
        ffmpeg, _ = ensure_binaries()
        return ffmpeg
    except RuntimeError as exc:
        raise VideoProcessingError(str(exc)) from exc


def resolve_ffprobe(settings: Settings) -> str:
    configured = settings.ffprobe_binary
    if configured:
        resolved = shutil.which(configured) or (configured if Path(configured).is_file() else None)
        if resolved:
            return str(resolved)
        raise VideoProcessingError(f"Configured FFprobe binary was not found: {configured}")

    try:
        _, ffprobe = ensure_binaries()
        return ffprobe
    except RuntimeError as exc:
        raise VideoProcessingError(str(exc)) from exc


def processing_capabilities(settings: Settings) -> dict[str, str | bool | None]:
    del settings
    return capabilities()


def probe_video(path: Path, settings: Settings) -> dict[str, float | int | None]:
    del settings
    metadata = probe(str(path))
    return {
        "duration_seconds": metadata["duration_seconds"],
        "fps": metadata["fps"],
        "frame_count": metadata["frame_count"],
    }


def extract_sampled_frames(
    video_path: Path,
    output_dir: Path,
    settings: Settings,
    sample_fps: float = 1.0,
    max_frames: int = 240,
) -> list[ExtractedFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame_%06d.jpg"
    command = [
        resolve_ffmpeg(settings),
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
    try:
        subprocess.run(command, capture_output=True, check=True, text=True, timeout=3600)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "FFmpeg could not decode this video").strip()
        raise VideoProcessingError(detail[-1200:]) from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoProcessingError("Video processing exceeded the one-hour limit") from exc

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
