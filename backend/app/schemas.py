from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


EvidenceType = Literal["neutral", "strength", "development_area"]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    sport_label: str | None = Field(default=None, max_length=80)


class OrganizationRead(ApiModel):
    id: str
    name: str
    sport_label: str | None
    created_at: datetime
    updated_at: datetime


class TeamCreate(BaseModel):
    organization_id: str
    name: str = Field(min_length=1, max_length=160)
    sport: str | None = Field(default=None, max_length=80)
    season: str | None = Field(default=None, max_length=80)
    metadata_json: dict[str, Any] | None = None


class TeamRead(ApiModel):
    id: str
    organization_id: str
    name: str
    sport: str | None
    season: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class AthleteCreate(BaseModel):
    organization_id: str
    team_id: str
    display_name: str = Field(min_length=1, max_length=160)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    jersey_number: str | None = Field(default=None, max_length=20)
    position: str | None = Field(default=None, max_length=80)
    external_id: str | None = Field(default=None, max_length=120)
    status: str = Field(default="active", max_length=40)


class AthleteRead(ApiModel):
    id: str
    organization_id: str
    team_id: str
    display_name: str
    first_name: str | None
    last_name: str | None
    jersey_number: str | None
    position: str | None
    external_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class EventCreate(BaseModel):
    organization_id: str
    team_id: str
    name: str = Field(min_length=1, max_length=180)
    sport: str | None = Field(default=None, max_length=80)
    opponent: str | None = Field(default=None, max_length=160)
    event_date: date | None = None
    location: str | None = Field(default=None, max_length=180)
    notes: str | None = None


class EventRead(ApiModel):
    id: str
    organization_id: str
    team_id: str
    name: str
    sport: str | None
    opponent: str | None
    event_date: date | None
    location: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class VideoCreate(BaseModel):
    organization_id: str
    team_id: str
    event_id: str | None = None
    title: str = Field(min_length=1, max_length=220)
    original_filename: str | None = Field(default=None, max_length=260)
    content_type: str | None = Field(default=None, max_length=120)
    storage_backend: str = Field(default="local", max_length=40)
    storage_key: str = Field(min_length=1, max_length=520)
    storage_url: str | None = Field(default=None, max_length=1000)
    duration_seconds: float | None = Field(default=None, ge=0)
    fps: float | None = Field(default=None, ge=0)
    frame_count: int | None = Field(default=None, ge=0)


class VideoRead(ApiModel):
    id: str
    organization_id: str
    team_id: str
    event_id: str | None
    title: str
    original_filename: str | None
    content_type: str | None
    storage_backend: str
    storage_key: str
    storage_url: str | None
    duration_seconds: float | None
    fps: float | None
    frame_count: int | None
    created_at: datetime
    updated_at: datetime


class ClipCreate(BaseModel):
    organization_id: str
    team_id: str
    event_id: str | None = None
    video_id: str
    title: str | None = Field(default=None, max_length=220)
    start_time_seconds: float = Field(ge=0)
    end_time_seconds: float = Field(ge=0)
    notes: str | None = None

    @field_validator("end_time_seconds")
    @classmethod
    def end_after_start(cls, value: float, info) -> float:
        start = info.data.get("start_time_seconds")
        if start is not None and value <= start:
            raise ValueError("end_time_seconds must be greater than start_time_seconds")
        return value


class ClipRead(ApiModel):
    id: str
    organization_id: str
    team_id: str
    event_id: str | None
    video_id: str
    title: str | None
    start_time_seconds: float
    end_time_seconds: float
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CategoryCreate(BaseModel):
    organization_id: str
    sport: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class CategoryRead(ApiModel):
    id: str
    organization_id: str
    sport: str | None
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class TagCreate(BaseModel):
    category_id: str
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class TagRead(ApiModel):
    id: str
    category_id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class EvidenceTagCreate(BaseModel):
    organization_id: str
    team_id: str
    athlete_id: str
    event_id: str | None = None
    video_id: str
    category_id: str
    tag_id: str
    timestamp_seconds: float = Field(ge=0)
    evidence_type: EvidenceType = "neutral"
    notes: str | None = None
    created_by: str | None = Field(default=None, max_length=120)
    clip_start_seconds: float | None = Field(default=None, ge=0)
    clip_end_seconds: float | None = Field(default=None, ge=0)

    @field_validator("clip_end_seconds")
    @classmethod
    def clip_end_after_clip_start(cls, value: float | None, info) -> float | None:
        start = info.data.get("clip_start_seconds")
        if value is not None and start is not None and value <= start:
            raise ValueError("clip_end_seconds must be greater than clip_start_seconds")
        return value


class EvidenceTagRead(ApiModel):
    id: str
    organization_id: str
    team_id: str
    athlete_id: str
    event_id: str | None
    video_id: str
    clip_id: str | None
    category_id: str
    tag_id: str
    timestamp_seconds: float
    evidence_type: EvidenceType
    notes: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class EvidenceTagDetail(EvidenceTagRead):
    athlete_name: str
    category_name: str
    tag_name: str
    video_title: str
    clip: ClipRead | None = None


class NoteCreate(BaseModel):
    organization_id: str
    team_id: str | None = None
    athlete_id: str | None = None
    video_id: str | None = None
    clip_id: str | None = None
    evidence_tag_id: str | None = None
    author_name: str | None = Field(default=None, max_length=120)
    body: str = Field(min_length=1)


class NoteRead(ApiModel):
    id: str
    organization_id: str
    team_id: str | None
    athlete_id: str | None
    video_id: str | None
    clip_id: str | None
    evidence_tag_id: str | None
    author_name: str | None
    body: str
    created_at: datetime
    updated_at: datetime


class BehaviorFrequency(BaseModel):
    category_id: str
    category_name: str
    tag_id: str
    tag_name: str
    evidence_count: int
    video_count: int
    event_count: int
    latest_timestamp_seconds: float | None = None


class AthleteProfile(ApiModel):
    athlete: AthleteRead
    strengths: list[BehaviorFrequency]
    development_areas: list[BehaviorFrequency]
    behavior_frequency: list[BehaviorFrequency]
    behavior_consistency: list[BehaviorFrequency]
    evidence_clips: list[EvidenceTagDetail]
    coach_notes: list[NoteRead]


class VisionTrackCreate(BaseModel):
    organization_id: str
    video_id: str
    athlete_id: str | None = None
    track_label: str | None = Field(default=None, max_length=160)
    source: str = Field(default="manual_sam3", max_length=80)
    status: str = Field(default="draft", max_length=40)
    frame_start: int = Field(ge=0)
    frame_end: int = Field(ge=0)
    bounding_data: dict[str, Any] = Field(default_factory=dict)
    segmentation_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("frame_end")
    @classmethod
    def frame_end_after_start(cls, value: int, info) -> int:
        start = info.data.get("frame_start")
        if start is not None and value < start:
            raise ValueError("frame_end must be greater than or equal to frame_start")
        return value


class VisionTrackRead(ApiModel):
    id: str
    organization_id: str
    video_id: str
    athlete_id: str | None
    track_label: str | None
    source: str
    status: str
    frame_start: int
    frame_end: int
    bounding_data: dict[str, Any]
    segmentation_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class VisionManualSelection(BaseModel):
    video_id: str
    athlete_id: str | None = None
    frame_number: int = Field(ge=0)
    prompt: dict[str, Any] = Field(default_factory=dict)


class VisionManualSelectionRead(BaseModel):
    status: str
    message: str
    video_id: str
    athlete_id: str | None
    frame_number: int
    prompt: dict[str, Any]

