from __future__ import annotations

import json
import subprocess
from pathlib import Path


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

