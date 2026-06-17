from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.core.config import Settings


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

    system_binary = shutil.which("ffmpeg")
    if system_binary:
        return system_binary

    try:
        import imageio_ffmpeg

        bundled_binary = imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise VideoProcessingError(
            "FFmpeg is unavailable. Install FFmpeg or install the imageio-ffmpeg backend dependency."
        ) from exc
    if not Path(bundled_binary).is_file():
        raise VideoProcessingError("The bundled FFmpeg executable could not be found")
    return bundled_binary


def resolve_ffprobe(settings: Settings) -> str | None:
    configured = settings.ffprobe_binary
    if configured:
        resolved = shutil.which(configured) or (configured if Path(configured).is_file() else None)
        return str(resolved) if resolved else None
    return shutil.which("ffprobe")


def processing_capabilities(settings: Settings) -> dict[str, str | bool | None]:
    try:
        ffmpeg = resolve_ffmpeg(settings)
    except VideoProcessingError as exc:
        return {"ready": False, "ffmpeg": None, "ffprobe": resolve_ffprobe(settings), "error": str(exc)}
    return {"ready": True, "ffmpeg": ffmpeg, "ffprobe": resolve_ffprobe(settings), "error": None}


def probe_video(path: Path, settings: Settings) -> dict[str, float | int | None]:
    ffprobe = resolve_ffprobe(settings)
    if not ffprobe:
        return _probe_with_bundled_ffmpeg(path)
    command = [
        ffprobe,
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
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return _probe_with_bundled_ffmpeg(path)

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return _probe_with_bundled_ffmpeg(path)
    stream = (payload.get("streams") or [{}])[0]
    duration = _float_or_none(stream.get("duration"))
    fps = _parse_rate(stream.get("avg_frame_rate"))
    frame_count = _int_or_none(stream.get("nb_frames"))
    return {"duration_seconds": duration, "fps": fps, "frame_count": frame_count}


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
        subprocess.run(command, capture_output=True, check=True, text=True, timeout=300)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "FFmpeg could not decode this video").strip()
        raise VideoProcessingError(detail[-1200:]) from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoProcessingError("Video processing exceeded the five-minute limit") from exc

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


def _probe_with_bundled_ffmpeg(path: Path) -> dict[str, float | int | None]:
    try:
        import imageio_ffmpeg

        frames = imageio_ffmpeg.read_frames(str(path), pix_fmt="rgb24")
        metadata = next(frames)
        frames.close()
    except (ImportError, OSError, RuntimeError, StopIteration):
        return {"duration_seconds": None, "fps": None, "frame_count": None}

    duration = _float_or_none(metadata.get("duration"))
    fps = _float_or_none(metadata.get("fps"))
    frame_count = round(duration * fps) if duration is not None and fps is not None else None
    return {"duration_seconds": duration, "fps": fps, "frame_count": frame_count}


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
