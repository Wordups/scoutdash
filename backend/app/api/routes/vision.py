from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
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
    # A seed is an anchor, not a pretend track. Until SAM3 responds, show the
    # coach's click only on the selected frame.
    frame_boxes = [
        {
            "frame_id": selected_frame.id,
            "frame_number": selected_frame.frame_number,
            "timestamp_seconds": selected_frame.timestamp_seconds,
            "box": box,
        }
    ]
    track = VisionTrackModel(
        organization_id=video.organization_id,
        video_id=video.id,
        athlete_id=payload.athlete_id,
        track_label=payload.track_label or (athlete.display_name if athlete else "Coach-selected player"),
        source="coach_click_sam3_seed",
        # Keep the long-standing track status for API compatibility. Detailed
        # SAM3 progress belongs in segmentation_metadata.status.
        status="track_seed",
        frame_start=selected_frame.frame_number,
        frame_end=selected_frame.frame_number,
        bounding_data={
            "selected_frame_id": selected_frame.id,
            "selected_frame_number": selected_frame.frame_number,
            "selected_timestamp_seconds": selected_frame.timestamp_seconds,
            "prompt": {"type": "point", "x_ratio": payload.x_ratio, "y_ratio": payload.y_ratio},
            "seed": {
                "frame_id": selected_frame.id,
                "frame_number": selected_frame.frame_number,
                "x_ratio": payload.x_ratio,
                "y_ratio": payload.y_ratio,
                "box_width_ratio": payload.box_width_ratio,
                "box_height_ratio": payload.box_height_ratio,
            },
            "frames": frame_boxes,
        },
        segmentation_metadata={
            "model": "sam3",
            "status": "sam3_adapter_not_configured",
            "coach_validation": "required",
            "note": "Track seed created from a coach click. Configure the SAM3 worker to continue tracking.",
        },
    )
    db.add(track)
    db.commit()
    db.refresh(track)

    # Hand the seed off to the SAM3 GPU worker (separate service). The backend
    # never imports sam3/torch. It just dispatches a job. If no worker is
    # configured the seed stands on its own (status stays
    # 'sam3_adapter_not_configured') so the coach still sees the click anchor.
    if settings.sam3_worker_url:
        job = _build_sam3_job(track, frames, selected_frame, video, payload)
        unavailable_reason = _sam3_job_unavailable_reason(job, settings)
        if unavailable_reason:
            _set_sam3_failed(track, unavailable_reason)
        else:
            attempt_id = uuid4().hex
            job["attempt_id"] = attempt_id
            track.status = "processing"
            track.segmentation_metadata = {
                **(track.segmentation_metadata or {}),
                "status": "sam3_processing",
                "attempt_id": attempt_id,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "note": "SAM3 tracking was queued for the selected player.",
            }
        db.add(track)
        db.commit()
        db.refresh(track)
        if not unavailable_reason:
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
    per-frame boxes. Guarded by a required shared internal token.

    Replaces each seed frame's box with the propagated box (matched on
    frame_number), drops frames where the object was not present, and flips the
    segmentation status to 'sam3_tracked'. coach_validation stays 'required',
    this is an assistive tracking layer, not behavior detection, so no ratings
    are invented here.
    """
    expected_token = settings.internal_api_token or ""
    if not expected_token or not hmac.compare_digest(x_internal_token or "", expected_token):
        raise HTTPException(status_code=401, detail="A valid internal token is required")

    track = db.get(VisionTrackModel, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")

    metadata = track.segmentation_metadata or {}
    current_attempt_id = metadata.get("attempt_id")
    if current_attempt_id:
        if payload.attempt_id != current_attempt_id:
            raise HTTPException(status_code=409, detail="This SAM3 result belongs to an older tracking attempt")
        if metadata.get("status") != "sam3_processing":
            raise HTTPException(status_code=409, detail="This SAM3 tracking attempt has already reached a terminal state")

    if payload.status == "sam3_failed":
        _set_sam3_failed(track, payload.error_message or "SAM3 could not finish this player track.")
        db.add(track)
        db.commit()
        db.refresh(track)
        return _track_timeline(track, db)

    boxes_by_frame = {frame.frame_number: frame.box for frame in payload.frames if frame.box}
    if not boxes_by_frame:
        _set_sam3_failed(track, payload.error_message or "SAM3 did not return a usable player mask for this frame window.")
        db.add(track)
        db.commit()
        db.refresh(track)
        return _track_timeline(track, db)

    bounding = dict(track.bounding_data or {})
    frame_rows = list(
        db.scalars(
            select(VideoFrameModel)
            .where(VideoFrameModel.video_id == track.video_id)
            .order_by(VideoFrameModel.frame_number.asc())
        )
    )
    kept_frames = []
    for frame in frame_rows:
        box = boxes_by_frame.get(frame.frame_number)
        if box is None:
            # Object absent on this frame, so drop it from the track.
            continue
        kept_frames.append(
            {
                "frame_id": frame.id,
                "frame_number": frame.frame_number,
                "timestamp_seconds": frame.timestamp_seconds,
                "box": box,
            }
        )
    bounding["frames"] = kept_frames
    track.bounding_data = bounding

    if not kept_frames:
        _set_sam3_failed(track, "SAM3 returned frames that do not belong to this film.")
        db.add(track)
        db.commit()
        db.refresh(track)
        return _track_timeline(track, db)

    track.frame_start = kept_frames[0]["frame_number"]
    track.frame_end = kept_frames[-1]["frame_number"]
    track.status = "tracked"

    track.segmentation_metadata = {
        **(track.segmentation_metadata or {}),
        "status": "sam3_tracked",
        "model": payload.model or (track.segmentation_metadata or {}).get("model", "sam3"),
        "version": payload.version,
        "coach_validation": "required",
        "frames_tracked": len(kept_frames),
        "tracked_at": datetime.now(timezone.utc).isoformat(),
        "error_message": None,
    }

    db.add(track)
    db.commit()
    db.refresh(track)
    return _track_timeline(track, db)


@router.post("/tracks/{track_id}/retry", response_model=VisionTrackTimeline)
def retry_track_segmentation(
    track_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VisionTrackTimeline:
    """Retry a failed player track without making the coach click the player again."""
    track = db.get(VisionTrackModel, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    if (track.segmentation_metadata or {}).get("status") == "sam3_processing":
        raise HTTPException(status_code=409, detail="This player track is already processing")
    if not settings.sam3_worker_url:
        raise HTTPException(status_code=409, detail="SAM3 worker is not configured")

    video = db.get(VideoModel, track.video_id)
    seed = (track.bounding_data or {}).get("seed")
    if video is None or not isinstance(seed, dict):
        raise HTTPException(status_code=409, detail="This player track has no retryable seed")
    selected_frame_id = seed.get("frame_id")
    selected_frame = db.get(VideoFrameModel, selected_frame_id) if isinstance(selected_frame_id, str) else None
    if selected_frame is None or selected_frame.video_id != video.id:
        raise HTTPException(status_code=409, detail="The original player-selection frame is unavailable")

    frames = list(
        db.scalars(
            select(VideoFrameModel)
            .where(VideoFrameModel.video_id == video.id)
            .order_by(VideoFrameModel.frame_number.asc())
        )
    )
    payload = PlayerTrackSeedCreate(
        video_id=video.id,
        athlete_id=track.athlete_id,
        frame_id=selected_frame.id,
        x_ratio=seed.get("x_ratio"),
        y_ratio=seed.get("y_ratio"),
        box_width_ratio=seed.get("box_width_ratio", 0.12),
        box_height_ratio=seed.get("box_height_ratio", 0.22),
        track_label=track.track_label,
    )
    job = _build_sam3_job(track, frames, selected_frame, video, payload)
    unavailable_reason = _sam3_job_unavailable_reason(job, settings)
    if unavailable_reason:
        _set_sam3_failed(track, unavailable_reason)
    else:
        attempt_id = uuid4().hex
        job["attempt_id"] = attempt_id
        track.status = "processing"
        bounding = dict(track.bounding_data or {})
        bounding["frames"] = [
            {
                "frame_id": selected_frame.id,
                "frame_number": selected_frame.frame_number,
                "timestamp_seconds": selected_frame.timestamp_seconds,
                "box": _box_from_click(
                    payload.x_ratio,
                    payload.y_ratio,
                    payload.box_width_ratio,
                    payload.box_height_ratio,
                ),
            }
        ]
        track.bounding_data = bounding
        track.segmentation_metadata = {
            **(track.segmentation_metadata or {}),
            "status": "sam3_processing",
            "attempt_id": attempt_id,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "error_message": None,
            "note": "SAM3 tracking was retried for the selected player.",
        }
    db.add(track)
    db.commit()
    db.refresh(track)
    if not unavailable_reason:
        background_tasks.add_task(_dispatch_sam3_job, settings.sam3_worker_url, settings.internal_api_token, job)
    return _track_timeline(track, db)


@router.get("/tracks/{track_id}/timeline", response_model=VisionTrackTimeline)
def get_track_timeline(track_id: str, db: Session = Depends(get_db)) -> VisionTrackTimeline:
    track = db.get(VisionTrackModel, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    _expire_stale_sam3_track(track, db)
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
    """Build a bounded, worker-reachable frame window around the coach click."""
    settings = get_settings()
    window = _track_window(frames, selected_frame.frame_number, settings.sam3_max_track_frames)
    return {
        "track_id": track.id,
        "video_id": video.id,
        "frames": [
            {
                "frame_number": frame.frame_number,
                "frame_url": _storage_url(video.storage_backend, frame.storage_key),
            }
            for frame in window
        ],
        "selected_frame_number": selected_frame.frame_number,
        "x_ratio": payload.x_ratio,
        "y_ratio": payload.y_ratio,
        "box_width_ratio": payload.box_width_ratio,
        "box_height_ratio": payload.box_height_ratio,
    }


def _dispatch_sam3_job(worker_url: str, internal_token: str | None, job: dict) -> None:
    """Fire-and-forget POST to the worker's dispatch endpoint (runs in a
    BackgroundTask). On any failure the track simply stays 'sam3_processing' and
    the coach keeps the click anchor. This is graceful degradation, never a 500."""
    import httpx

    headers = {"X-Internal-Token": internal_token or ""}
    try:
        response = httpx.post(worker_url, json=job, headers=headers, timeout=httpx.Timeout(120.0, connect=30.0))
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("SAM3 dispatch was rejected for track %s: %s", job.get("track_id"), exc)
        _mark_sam3_track_failed(
            str(job.get("track_id", "")),
            str(job.get("attempt_id", "")),
            "ScoutDash could not reach the SAM3 worker. Check the worker URL and shared token.",
        )
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        # A cold Modal endpoint can accept a spawn just before the caller's
        # request times out. Keep the attempt processing until its callback or
        # normal expiry rather than incorrectly overwriting a real result.
        logger.warning("SAM3 dispatch acknowledgement is delayed for track %s: %s", job.get("track_id"), exc)


def _track_window(
    frames: list[VideoFrameModel], selected_frame_number: int, max_frames: int
) -> list[VideoFrameModel]:
    """Keep the selected frame centered in a bounded tracking window."""
    selected_index = next(
        (index for index, frame in enumerate(frames) if frame.frame_number == selected_frame_number),
        None,
    )
    if selected_index is None:
        raise ValueError("Selected frame is not present in the film frame list")
    if len(frames) <= max_frames:
        return frames

    start = max(0, selected_index - max_frames // 2)
    end = start + max_frames
    if end > len(frames):
        end = len(frames)
        start = end - max_frames
    return frames[start:end]


def _sam3_job_unavailable_reason(job: dict, settings: Settings) -> str | None:
    frames = job.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        return "SAM3 needs at least two film frames around the selected player. Break down more film first."

    for frame in frames:
        if not isinstance(frame, dict) or not _is_worker_reachable_url(frame.get("frame_url")):
            return "SAM3 needs public frame storage. Upload film to persistent object storage instead of localhost."
    if not settings.internal_api_token:
        return "SAM3 needs an internal worker token before tracking can start."
    return None


def _is_worker_reachable_url(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "minio", "backend"} or host.endswith(".local"):
        return False
    if "." not in host:
        return False
    try:
        address = ip_address(host)
    except ValueError:
        return True
    return not (address.is_loopback or address.is_private or address.is_link_local or address.is_unspecified)


def _set_sam3_failed(track: VisionTrackModel, message: str) -> None:
    track.status = "failed"
    track.segmentation_metadata = {
        **(track.segmentation_metadata or {}),
        "status": "sam3_failed",
        "error_message": message[:600],
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "coach_validation": "required",
    }


def _mark_sam3_track_failed(track_id: str, attempt_id: str, message: str) -> None:
    if not track_id or not attempt_id:
        return
    with SessionLocal() as background_db:
        track = background_db.get(VisionTrackModel, track_id)
        if track is None:
            return
        metadata = track.segmentation_metadata or {}
        if metadata.get("attempt_id") != attempt_id or metadata.get("status") != "sam3_processing":
            return
        _set_sam3_failed(track, message)
        background_db.commit()


def _expire_stale_sam3_track(track: VisionTrackModel, db: Session) -> None:
    metadata = track.segmentation_metadata or {}
    if metadata.get("status") != "sam3_processing":
        return
    requested_at = metadata.get("requested_at")
    if not isinstance(requested_at, str):
        return
    try:
        started_at = datetime.fromisoformat(requested_at)
    except ValueError:
        return
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    timeout = timedelta(seconds=get_settings().sam3_track_timeout_seconds)
    if datetime.now(timezone.utc) - started_at < timeout:
        return
    _set_sam3_failed(track, "SAM3 tracking timed out. Retry after checking the worker and frame storage.")
    db.add(track)
    db.commit()
