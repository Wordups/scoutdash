import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from app.api.routes import athletes, clips, evidence, events, notes, organizations, taxonomy, teams, videos, vision
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.models import (  # noqa: F401
    AthleteModel,
    CategoryModel,
    ClipModel,
    EventModel,
    EvidenceTagModel,
    NoteModel,
    OrganizationModel,
    TagModel,
    TeamModel,
    VideoModel,
    VisionTrackModel,
)


settings = get_settings()


def _initialize_database() -> None:
    last_error: OperationalError | None = None
    for _ in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(2)
    if last_error is not None:
        raise last_error


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.local_upload_dir.mkdir(parents=True, exist_ok=True)
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
