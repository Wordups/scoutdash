"""Small, dependency-free helpers for the ScoutDash SAM3 worker.

Keeping the payload and predictor-output handling here lets us test the
integration contract without importing Modal or loading a GPU model.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def normalize_job(job: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a tracking job and return it with ordered frame metadata."""
    track_id = job.get("track_id")
    if not isinstance(track_id, str) or not track_id.strip():
        raise ValueError("track_id is required")

    attempt_id = job.get("attempt_id")
    if not isinstance(attempt_id, str) or not attempt_id.strip():
        raise ValueError("attempt_id is required")

    raw_frames = job.get("frames")
    if not isinstance(raw_frames, list) or len(raw_frames) < 2:
        raise ValueError("at least two ordered frames are required for tracking")

    frames: list[dict[str, Any]] = []
    frame_numbers: set[int] = set()
    for raw_frame in raw_frames:
        if not isinstance(raw_frame, Mapping):
            raise ValueError("every frame must be an object")
        frame_number = raw_frame.get("frame_number")
        frame_url = raw_frame.get("frame_url")
        if isinstance(frame_number, bool) or not isinstance(frame_number, int):
            raise ValueError("every frame needs an integer frame_number")
        if frame_number in frame_numbers:
            raise ValueError("frame numbers must be unique")
        if not isinstance(frame_url, str) or not frame_url.strip():
            raise ValueError("every frame needs a public frame_url")
        frame_numbers.add(frame_number)
        frames.append({"frame_number": frame_number, "frame_url": frame_url})

    frames.sort(key=lambda item: item["frame_number"])
    selected_frame_number = job.get("selected_frame_number")
    if isinstance(selected_frame_number, bool) or not isinstance(selected_frame_number, int):
        raise ValueError("selected_frame_number is required")
    try:
        selected_frame_index = next(
            index for index, frame in enumerate(frames) if frame["frame_number"] == selected_frame_number
        )
    except StopIteration as exc:
        raise ValueError("selected_frame_number is not present in frames") from exc

    normalized = dict(job)
    normalized["frames"] = frames
    normalized["selected_frame_index"] = selected_frame_index
    normalized["x_ratio"] = _ratio(job.get("x_ratio"), "x_ratio")
    normalized["y_ratio"] = _ratio(job.get("y_ratio"), "y_ratio")
    normalized["box_width_ratio"] = _ratio(job.get("box_width_ratio", 0.12), "box_width_ratio", positive=True)
    normalized["box_height_ratio"] = _ratio(job.get("box_height_ratio", 0.22), "box_height_ratio", positive=True)
    return normalized


def box_from_predictor_output(outputs: Mapping[str, Any], object_id: int) -> dict[str, float] | None:
    """Return one normalized xywh box from SAM3's documented output payload."""
    object_ids = _as_list(outputs.get("out_obj_ids"))
    boxes = _as_list(outputs.get("out_boxes_xywh"))
    if not isinstance(object_ids, list) or not isinstance(boxes, list):
        return None

    for candidate_id, candidate_box in zip(object_ids, boxes, strict=False):
        try:
            matches_object = int(candidate_id) == object_id
        except (TypeError, ValueError):
            continue
        if not matches_object:
            continue
        values = _as_list(candidate_box)
        if not isinstance(values, list) or len(values) != 4:
            return None
        return _normalized_box(values)
    return None


def _ratio(value: Any, name: str, *, positive: bool = False) -> float:
    try:
        ratio = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(ratio) or ratio < 0 or ratio > 1 or (positive and ratio <= 0):
        raise ValueError(f"{name} must be between 0 and 1")
    return ratio


def _as_list(value: Any) -> Any:
    return value.tolist() if hasattr(value, "tolist") else value


def _normalized_box(values: list[Any]) -> dict[str, float] | None:
    try:
        x, y, width, height = (float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in (x, y, width, height)):
        return None

    x = min(1.0, max(0.0, x))
    y = min(1.0, max(0.0, y))
    width = min(1.0 - x, max(0.0, width))
    height = min(1.0 - y, max(0.0, height))
    if width <= 0 or height <= 0:
        return None
    return {"x": x, "y": y, "width": width, "height": height}
