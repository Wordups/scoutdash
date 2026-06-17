from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class ManualSelection:
    video_id: str
    frame_number: int
    prompt: dict[str, Any]
    athlete_id: str | None = None


@dataclass(frozen=True)
class SegmentationMetadata:
    model_name: str
    model_version: str | None = None
    prompt_type: str | None = None
    mask_ref: str | None = None
    confidence: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrackFrame:
    frame_number: int
    bounding_box: BoundingBox
    segmentation: SegmentationMetadata | None = None


@dataclass(frozen=True)
class AthleteTrack:
    video_id: str
    frame_start: int
    frame_end: int
    frames: list[TrackFrame]
    athlete_id: str | None = None
    track_label: str | None = None
    source: str = "manual_sam3"

