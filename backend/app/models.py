from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrganizationModel(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sport_label: Mapped[str | None] = mapped_column(String(80))

    teams: Mapped[list[TeamModel]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    athletes: Mapped[list[AthleteModel]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    events: Mapped[list[EventModel]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    videos: Mapped[list[VideoModel]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    categories: Mapped[list[CategoryModel]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    evidence_tags: Mapped[list[EvidenceTagModel]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    athlete_reports: Mapped[list[AthleteReportModel]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class TeamModel(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sport: Mapped[str | None] = mapped_column(String(80), index=True)
    season: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    organization: Mapped[OrganizationModel] = relationship(back_populates="teams")
    athletes: Mapped[list[AthleteModel]] = relationship(back_populates="team", cascade="all, delete-orphan")
    events: Mapped[list[EventModel]] = relationship(back_populates="team", cascade="all, delete-orphan")
    videos: Mapped[list[VideoModel]] = relationship(back_populates="team", cascade="all, delete-orphan")


class AthleteModel(TimestampMixin, Base):
    __tablename__ = "athletes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    jersey_number: Mapped[str | None] = mapped_column(String(20))
    position: Mapped[str | None] = mapped_column(String(80))
    external_id: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), default="active")

    organization: Mapped[OrganizationModel] = relationship(back_populates="athletes")
    team: Mapped[TeamModel] = relationship(back_populates="athletes")
    evidence_tags: Mapped[list[EvidenceTagModel]] = relationship(back_populates="athlete")
    notes: Mapped[list[NoteModel]] = relationship(back_populates="athlete")
    vision_tracks: Mapped[list[VisionTrackModel]] = relationship(back_populates="athlete")
    reports: Mapped[list[AthleteReportModel]] = relationship(back_populates="athlete")


class EventModel(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    sport: Mapped[str | None] = mapped_column(String(80), index=True)
    opponent: Mapped[str | None] = mapped_column(String(160))
    event_date: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(180))
    notes: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[OrganizationModel] = relationship(back_populates="events")
    team: Mapped[TeamModel] = relationship(back_populates="events")
    videos: Mapped[list[VideoModel]] = relationship(back_populates="event")
    clips: Mapped[list[ClipModel]] = relationship(back_populates="event")


class VideoModel(TimestampMixin, Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(260))
    content_type: Mapped[str | None] = mapped_column(String(120))
    storage_backend: Mapped[str] = mapped_column(String(40), default="local")
    storage_key: Mapped[str] = mapped_column(String(520), nullable=False)
    storage_url: Mapped[str | None] = mapped_column(String(1000))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    fps: Mapped[float | None] = mapped_column(Float)
    frame_count: Mapped[int | None] = mapped_column(Integer)

    organization: Mapped[OrganizationModel] = relationship(back_populates="videos")
    team: Mapped[TeamModel] = relationship(back_populates="videos")
    event: Mapped[EventModel | None] = relationship(back_populates="videos")
    clips: Mapped[list[ClipModel]] = relationship(back_populates="video", cascade="all, delete-orphan")
    evidence_tags: Mapped[list[EvidenceTagModel]] = relationship(back_populates="video")
    frames: Mapped[list[VideoFrameModel]] = relationship(back_populates="video", cascade="all, delete-orphan")
    vision_tracks: Mapped[list[VisionTrackModel]] = relationship(back_populates="video")


class ClipModel(TimestampMixin, Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), index=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(220))
    start_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    video: Mapped[VideoModel] = relationship(back_populates="clips")
    event: Mapped[EventModel | None] = relationship(back_populates="clips")
    evidence_tags: Mapped[list[EvidenceTagModel]] = relationship(back_populates="clip")
    notes_list: Mapped[list[NoteModel]] = relationship(back_populates="clip")


class CategoryModel(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("organization_id", "sport", "name", name="uq_category_org_sport_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sport: Mapped[str | None] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[OrganizationModel] = relationship(back_populates="categories")
    tags: Mapped[list[TagModel]] = relationship(back_populates="category", cascade="all, delete-orphan")
    evidence_tags: Mapped[list[EvidenceTagModel]] = relationship(back_populates="category")


class TagModel(TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_tag_category_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    category: Mapped[CategoryModel] = relationship(back_populates="tags")
    evidence_tags: Mapped[list[EvidenceTagModel]] = relationship(back_populates="tag")


class EvidenceTagModel(TimestampMixin, Base):
    __tablename__ = "evidence_tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    athlete_id: Mapped[str] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), index=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    clip_id: Mapped[str | None] = mapped_column(ForeignKey("clips.id", ondelete="SET NULL"), index=True)
    category_id: Mapped[str] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id", ondelete="RESTRICT"), nullable=False, index=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(40), default="neutral", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(120))

    organization: Mapped[OrganizationModel] = relationship(back_populates="evidence_tags")
    athlete: Mapped[AthleteModel] = relationship(back_populates="evidence_tags")
    video: Mapped[VideoModel] = relationship(back_populates="evidence_tags")
    clip: Mapped[ClipModel | None] = relationship(back_populates="evidence_tags")
    category: Mapped[CategoryModel] = relationship(back_populates="evidence_tags")
    tag: Mapped[TagModel] = relationship(back_populates="evidence_tags")


class NoteModel(TimestampMixin, Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[str | None] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[str | None] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    clip_id: Mapped[str | None] = mapped_column(ForeignKey("clips.id", ondelete="CASCADE"), index=True)
    evidence_tag_id: Mapped[str | None] = mapped_column(
        ForeignKey("evidence_tags.id", ondelete="CASCADE"), index=True
    )
    author_name: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text, nullable=False)

    athlete: Mapped[AthleteModel | None] = relationship(back_populates="notes")
    clip: Mapped[ClipModel | None] = relationship(back_populates="notes_list")


class VisionTrackModel(TimestampMixin, Base):
    __tablename__ = "vision_tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    athlete_id: Mapped[str | None] = mapped_column(ForeignKey("athletes.id", ondelete="SET NULL"), index=True)
    track_label: Mapped[str | None] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(80), default="manual_sam3")
    status: Mapped[str] = mapped_column(String(40), default="draft")
    frame_start: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_end: Mapped[int] = mapped_column(Integer, nullable=False)
    bounding_data: Mapped[dict] = mapped_column(JSON, default=dict)
    segmentation_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    video: Mapped[VideoModel] = relationship(back_populates="vision_tracks")
    athlete: Mapped[AthleteModel | None] = relationship(back_populates="vision_tracks")


class VideoFrameModel(TimestampMixin, Base):
    __tablename__ = "video_frames"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(520), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    video: Mapped[VideoModel] = relationship(back_populates="frames")


class AthleteReportModel(TimestampMixin, Base):
    __tablename__ = "athlete_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    athlete_id: Mapped[str] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    report_type: Mapped[str] = mapped_column(String(80), default="athlete_development")
    status: Mapped[str] = mapped_column(String(40), default="generated")
    generated_by: Mapped[str | None] = mapped_column(String(120))
    report_data: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_tag_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    note_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    organization: Mapped[OrganizationModel] = relationship(back_populates="athlete_reports")
    athlete: Mapped[AthleteModel] = relationship(back_populates="reports")
