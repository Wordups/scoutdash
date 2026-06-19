import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app.api.routes import athletes, clips, evidence, events, notes, organizations, reports, taxonomy, teams, videos, vision
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (  # noqa: F401
    AthleteModel,
    AthleteReportModel,
    CategoryModel,
    ClipModel,
    EventModel,
    EvidenceTagModel,
    NoteModel,
    OrganizationModel,
    TagModel,
    TeamModel,
    VideoFrameModel,
    VideoModel,
    VideoProcessingJobModel,
    VisionTrackModel,
)
from app.services.film_metadata import capabilities, ensure_binaries


settings = get_settings()


def _initialize_database() -> None:
    last_error: OperationalError | None = None
    for _ in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            _ensure_video_metadata_columns()
            _fail_interrupted_video_jobs()
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(2)
    if last_error is not None:
        raise last_error


def _ensure_video_metadata_columns() -> None:
    existing = {column["name"] for column in inspect(engine).get_columns("videos")}
    additions = {
        "width": "INTEGER",
        "height": "INTEGER",
        "codec": "VARCHAR(80)",
        "container_format": "VARCHAR(120)",
        "creation_time": "VARCHAR(80)",
    }
    with engine.begin() as connection:
        for name, sql_type in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE videos ADD COLUMN {name} {sql_type}"))


def _fail_interrupted_video_jobs() -> None:
    with SessionLocal() as db:
        jobs = (
            db.query(VideoProcessingJobModel)
            .filter(VideoProcessingJobModel.status.in_(("queued", "processing")))
            .all()
        )
        if not jobs:
            return
        completed_at = datetime.now(timezone.utc)
        for job in jobs:
            job.status = "failed"
            job.error_message = "Film breakdown was interrupted. Start it again."
            job.completed_at = completed_at
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.local_upload_dir.mkdir(parents=True, exist_ok=True)
    ensure_binaries()
    _initialize_database()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.local_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.local_upload_dir), name="media")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/capabilities")
def capability_healthcheck() -> dict[str, object]:
    storage_persistent = settings.storage_backend == "s3" or settings.local_storage_persistent
    return {
        "status": "ok",
        "storage_backend": settings.storage_backend,
        "storage_configured": settings.storage_backend == "local" or bool(settings.s3_bucket),
        "storage_persistent": storage_persistent,
        "video_processing": capabilities(),
    }


app.include_router(organizations.router, prefix=settings.api_prefix)
app.include_router(teams.router, prefix=settings.api_prefix)
app.include_router(athletes.router, prefix=settings.api_prefix)
app.include_router(events.router, prefix=settings.api_prefix)
app.include_router(videos.router, prefix=settings.api_prefix)
app.include_router(clips.router, prefix=settings.api_prefix)
app.include_router(taxonomy.router, prefix=settings.api_prefix)
app.include_router(evidence.router, prefix=settings.api_prefix)
app.include_router(notes.router, prefix=settings.api_prefix)
app.include_router(vision.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
