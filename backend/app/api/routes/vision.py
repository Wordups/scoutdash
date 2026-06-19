from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.models import AthleteModel, OrganizationModel, VideoFrameModel, VideoModel, VisionTrackModel
from app.schemas import (
    AthleteRead,
    PlayerTrackSeedCreate,
    TrackSegmentationWriteback,
    TrackTimelineMoment,
    VideoRead,
    VisionManualSelection,
    VisionManualSelectionRead,
    VisionTrackCreate,
    VisionTrackRead,
    VisionTrackTimeline,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vision", tags=["vision"])


@router.get("/tracks", response_model=list[VisionTrackRead])
def list_tracks(
    organization_id: str | None = Query(default=None),
    video_id: str | None = Query(default=None),
    athlete_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[VisionTrackModel]:
    statement = select(VisionTrackModel)
    if organization_id:
        statement = statement.where(VisionTrackModel.organization_id == organization_id)
    if video_id:
        statement = statement.where(VisionTrackModel.video_id == video_id)
    if athlete_id:
        statement = statement.where(VisionTrackModel.athlete_id == athlete_id)
    return list(db.scalars(statement.order_by(VisionTrackModel.created_at.desc())))


@router.post("/tracks", response_model=VisionTrackRead, status_code=201)
def create_track(payload: VisionTrackCreate, db: Session = Depends(get_db)) -> VisionTrackModel:
    if db.get(OrganizationModel, payload.organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    video = db.get(VideoModel, payload.video_id)
    if video is None or video.organization_id != payload.organization_id:
        raise HTTPException(status_code=404, detail="Video not found for organization")
    athlete = db.get(AthleteModel, payload.athlete_id) if payload.athlete_id else None
    if payload.athlete_id and (athlete is None or athlete.organization_id != payload.organization_id):
        raise HTTPException(status_code=404, detail="Athlete not found for organization")
    track = VisionTrackModel(**payload.model_dump())
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


@router.post("/manual-selections", response_model=VisionManualSelectionRead)
def create_manual_selection(payload: VisionManualSelection, db: Session = Depends(get_db)) -> VisionManualSelectionRead:
    video = db.get(VideoModel, payload.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    athlete = db.get(AthleteModel, payload.athlete_id) if payload.athlete_id else None
    if payload.athlete_id and (athlete is None or athlete.organization_id != video.organization_id):
        raise HTTPException(status_code=404, detail="Athlete not found for video organization")
    return VisionManualSelectionRead(
        status="queued_for_segmentation",
        message="Manual selection captured. SAM3 segmentation is an assistive layer and is not running behavior detection.",
        video_id=payload.video_id,
        athlete_id=payload.athlete_id,
        frame_number=payload.frame_number,
        prompt=payload.prompt,
    )


@router.post("/track-seeds", response_model=VisionTrackTimeline, status_code=201)
def create_player_track_seed(
    payload: PlayerTrackSeedCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VisionTrackTimeline:
    video = db.get(VideoModel, payload.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    selected_frame = db.get(VideoFrameModel, payload.frame_id)
    if selected_frame is None or selected_frame.video_id != video.id:
        raise HTTPException(status_code=404, detail="Frame not found for video")
    athlete = db.get(AthleteModel, payload.athlete_id) if payload.athlete_id else None
    if payload.athlete_id and (athlete is None or athlete.organization_id != video.organization_id):
        raise HTTPException(status_code=404, detail="Athlete not found for video organization")

    frames = list(
        db.scalars(
            select(VideoFrameModel)
            .where(VideoFrameModel.video_id == video.id)
            .order_by(VideoFrameModel.frame_number.asc())
        )
    )
    if not frames:
        raise HTTPException(status_code=400, detail="Process video before creating a track seed")

    box = _box_from_click(
        payload.x_ratio,
        payload.y_ratio,
        payload.box_width_ratio,
        payload.box_height_ratio,
    )
    frame_boxes = [
        {
            "frame_id": frame.id,
            "frame_number": frame.frame_number,
            "timestamp_seconds": frame.timestamp_seconds,
            "box": box,
        }
        for frame in frames
    ]
    track = VisionTrackModel(
        organization_id=video.organization_id,
        video_id=video.id,
        athlete_id=payload.athlete_id,
        track_label=payload.track_label or (athlete.display_name if athlete else "Coach-selected player"),
        source="coach_click_sam3_seed",
        status="track_seed",
        frame_start=frames[0].frame_number,
        frame_end=frames[-1].frame_number,
        bounding_data={
            "selected_frame_id": selected_frame.id,
            "selected_frame_number": selected_frame.frame_number,
            "selected_timestamp_seconds": selected_frame.timestamp_seconds,
            "prompt": {"type": "point", "x_ratio": payload.x_ratio, "y_ratio": payload.y_ratio},
            "frames": frame_boxes,
        },
        segmentation_metadata={
            "model": "sam3",
            "status": "sam3_adapter_not_configured",
            "coach_validation": "required",
            "note": "Track seed created from coach click. Wire SAM3 adapter here for mask propagation.",
        },
    )
    db.add(track)
    db.commit()
    db.refresh(track)

    # Hand the seed off to the SAM3 GPU worker (separate service). The backend
    # never imports sam3/torch — it just dispatches a job. If no worker is
    # configured the seed stands on its own (status stays
    # 'sam3_adapter_not_configured') so the coach still sees the click anchor.
    if settings.sam3_worker_url:
        job = _build_sam3_job(track, frames, selected_frame, video, payload)
        track.segmentation_metadata = {
            **(track.segmentation_metadata or {}),
            "status": "sam3_processing",
            "note": "Track seed created; SAM3 tracking dispatched to the GPU worker.",
        }
        db.add(track)
        db.commit()
        db.refresh(track)
        background_tasks.add_task(
            _dispatch_sam3_job,
            settings.sam3_worker_url,
            settings.internal_api_token,
            job,
        )

    return _track_timeline(track, db)


@router.post("/tracks/{track_id}/segmentation", response_model=VisionTrackTimeline)
def write_track_segmentation(
    track_id: str,
    payload: TrackSegmentationWriteback,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> VisionTrackTimeline:
    """Internal write-back endpoint the SAM3 GPU worker calls with propagated,
    per-frame boxes. Guarded by a shared internal token when one is configured.

    Replaces each seed frame's box with the propagated box (matched on
    frame_number), drops frames where the object was not present, and flips the
    segmentation status to 'sam3_tracked'. coach_validation stays 'required' —
    this is an assistive tracking layer, not behavior detection, so no ratings
    are invented here.
    """
    if settings.internal_api_token and x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=401, detail="Invalid internal token")

    track = db.get(VisionTrackModel, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")

    boxes_by_frame = {frame.frame_number: frame.box for frame in payload.frames if frame.box}

    bounding = dict(track.bounding_data or {})
    kept_frames = []
    for item in bounding.get("frames", []):
        box = boxes_by_frame.get(item.get("frame_number"))
        if box is None:
            # Object absent on this frame — drop it from the track.
            continue
        kept_frames.append({**item, "box": box})
    bounding["frames"] = kept_frames
    track.bounding_data = bounding

    if kept_frames:
        track.frame_start = kept_frames[0]["frame_number"]
        track.frame_end = kept_frames[-1]["frame_number"]
        track.status = "tracked"

    track.segmentation_metadata = {
        **(track.segmentation_metadata or {}),
        "status": payload.status or "sam3_tracked",
        "model": payload.model or (track.segmentation_metadata or {}).get("model", "sam3"),
        "version": payload.version,
        "coach_validation": "required",
        "frames_tracked": len(kept_frames),
        "tracked_at": datetime.now(timezone.utc).isoformat(),
    }

    db.add(track)
    db.commit()
    db.refresh(track)
    return _track_timeline(track, db)


@router.get("/tracks/{track_id}/timeline", response_model=VisionTrackTimeline)
def get_track_timeline(track_id: str, db: Session = Depends(get_db)) -> VisionTrackTimeline:
    track = db.get(VisionTrackModel, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return _track_timeline(track, db)


def _track_timeline(track: VisionTrackModel, db: Session) -> VisionTrackTimeline:
    video = db.get(VideoModel, track.video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    athlete = db.get(AthleteModel, track.athlete_id) if track.athlete_id else None
    frame_ids = [item.get("frame_id") for item in (track.bounding_data or {}).get("frames", []) if item.get("frame_id")]
    frames_by_id = {}
    if frame_ids:
        frame_rows = list(db.scalars(select(VideoFrameModel).where(VideoFrameModel.id.in_(frame_ids))))
        frames_by_id = {frame.id: frame for frame in frame_rows}
    moments: list[TrackTimelineMoment] = []
    for item in (track.bounding_data or {}).get("frames", []):
        frame_id = item.get("frame_id")
        frame = frames_by_id.get(frame_id)
        moments.append(
            TrackTimelineMoment(
                frame_id=frame_id,
                frame_number=item["frame_number"],
                timestamp_seconds=item["timestamp_seconds"],
                frame_url=_frame_url(frame, video) if frame else None,
                box=item["box"],
            )
        )
    return VisionTrackTimeline(
        track=VisionTrackRead.model_validate(track),
        athlete=AthleteRead.model_validate(athlete) if athlete else None,
        video=VideoRead.model_validate(video).model_copy(
            update={"storage_url": _storage_url(video.storage_backend, video.storage_key)}
        ),
        moments=moments,
    )


def _box_from_click(x: float, y: float, width: float, height: float) -> dict[str, float]:
    left = max(0.0, min(1.0 - width, x - width / 2))
    top = max(0.0, min(1.0 - height, y - height / 2))
    return {"x": left, "y": top, "width": width, "height": height}


def _frame_url(frame: VideoFrameModel | None, video: VideoModel) -> str | None:
    if frame is None:
        return None

    return _storage_url(video.storage_backend, frame.storage_key)


def _storage_url(backend: str, storage_key: str) -> str | None:
    from app.core.config import get_settings
    from app.services.storage import storage_url

    settings = get_settings()
    return storage_url(settings, backend, storage_key)


def _build_sam3_job(
    track: VisionTrackModel,
    frames: list[VideoFrameModel],
    selected_frame: VideoFrameModel,
    video: VideoModel,
    payload: PlayerTrackSeedCreate,
) -> dict:
    """Job payload the GPU worker consumes: ordered frame URLs + the coach click.

    The worker downloads the frames as 0.jpg..N.jpg (its SAM3 video-tracker input
    format), prompts the tracker on the selected frame with (x_ratio, y_ratio) as
    relative coords, propagates, and POSTs boxes back to the segmentation endpoint.
    """
    return {
        "track_id": track.id,
        "video_id": video.id,
        "frames": [
            {
                "frame_number": frame.frame_number,
                "frame_url": _storage_url(video.storage_backend, frame.storage_key),
            }
            for frame in frames
        ],
        "selected_frame_number": selected_frame.frame_number,
        "x_ratio": payload.x_ratio,
        "y_ratio": payload.y_ratio,
    }


def _dispatch_sam3_job(worker_url: str, internal_token: str | None, job: dict) -> None:
    """Fire-and-forget POST to the worker's dispatch endpoint (runs in a
    BackgroundTask). On any failure the track simply stays 'sam3_processing' and
    the coach keeps the click anchor — graceful degradation, never a 500."""
    import httpx

    headers = {"X-Internal-Token": internal_token} if internal_token else {}
    try:
        response = httpx.post(worker_url, json=job, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - worker outage must not break the seed
        logger.warning("SAM3 dispatch failed for track %s: %s", job.get("track_id"), exc)
