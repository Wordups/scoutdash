"""Tests for the SAM3 track-seed → write-back flow.

The GPU worker is never exercised here (it lives in services/sam3-worker and needs a GPU).
These cover the backend contract: the seed degrades gracefully with no worker configured,
and the internal write-back endpoint replaces boxes / drops absent frames / flips status.
"""

from app.db.session import SessionLocal
from app.models import OrganizationModel, TeamModel, VideoFrameModel, VideoModel


INTERNAL_HEADERS = {"X-Internal-Token": "test-internal-token"}


def _seed_video():
    db = SessionLocal()
    try:
        org = OrganizationModel(name="Org")
        db.add(org)
        db.flush()
        team = TeamModel(organization_id=org.id, name="Team")
        db.add(team)
        db.flush()
        video = VideoModel(
            organization_id=org.id,
            team_id=team.id,
            title="Game film",
            storage_backend="local",
            storage_key="videos/v.mp4",
        )
        db.add(video)
        db.flush()
        frames = []
        for n in range(3):
            frame = VideoFrameModel(
                video_id=video.id,
                frame_number=n,
                timestamp_seconds=float(n),
                storage_key=f"frames/{n}.jpg",
                width=1920,
                height=1080,
            )
            db.add(frame)
            frames.append(frame)
        db.commit()
        return video.id, frames[0].id
    finally:
        db.close()


def test_track_seed_degrades_without_worker(client):
    video_id, selected_frame_id = _seed_video()
    resp = client.post(
        "/api/vision/track-seeds",
        json={"video_id": video_id, "frame_id": selected_frame_id, "x_ratio": 0.5, "y_ratio": 0.5},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # No SAM3_WORKER_URL configured in tests -> seed stands alone, coach still sees the anchor.
    assert body["track"]["segmentation_metadata"]["status"] == "sam3_adapter_not_configured"
    assert len(body["moments"]) == 1
    assert body["moments"][0]["frame_id"] == selected_frame_id


def test_segmentation_writeback_replaces_boxes_and_drops_absent(client):
    video_id, selected_frame_id = _seed_video()
    seed = client.post(
        "/api/vision/track-seeds",
        json={"video_id": video_id, "frame_id": selected_frame_id, "x_ratio": 0.5, "y_ratio": 0.5},
    )
    track_id = seed.json()["track"]["id"]

    # Worker propagated boxes for frames 0 and 2; the object was absent on frame 1.
    resp = client.post(
        f"/api/vision/tracks/{track_id}/segmentation",
        json={
            "status": "sam3_tracked",
            "model": "sam3",
            "version": "test-revision",
            "frames": [
                {"frame_number": 0, "box": {"x": 0.10, "y": 0.10, "width": 0.20, "height": 0.30}},
                {"frame_number": 2, "box": {"x": 0.40, "y": 0.45, "width": 0.18, "height": 0.28}},
            ],
        },
        headers=INTERNAL_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    out = resp.json()

    assert out["track"]["segmentation_metadata"]["status"] == "sam3_tracked"
    assert out["track"]["segmentation_metadata"]["coach_validation"] == "required"
    assert out["track"]["segmentation_metadata"]["frames_tracked"] == 2

    nums = [m["frame_number"] for m in out["moments"]]
    assert nums == [0, 2]  # frame 1 (object absent) was dropped

    box0 = next(m["box"] for m in out["moments"] if m["frame_number"] == 0)
    assert box0 == {"x": 0.10, "y": 0.10, "width": 0.20, "height": 0.30}
    assert out["track"]["frame_start"] == 0
    assert out["track"]["frame_end"] == 2


def test_segmentation_writeback_requires_token_when_configured(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "internal_api_token", "secret-token")

    video_id, selected_frame_id = _seed_video()
    track_id = client.post(
        "/api/vision/track-seeds",
        json={"video_id": video_id, "frame_id": selected_frame_id, "x_ratio": 0.5, "y_ratio": 0.5},
    ).json()["track"]["id"]

    bad = client.post(
        f"/api/vision/tracks/{track_id}/segmentation",
        json={"frames": []},
        headers={"X-Internal-Token": "wrong"},
    )
    assert bad.status_code == 401

    ok = client.post(
        f"/api/vision/tracks/{track_id}/segmentation",
        json={"frames": []},
        headers={"X-Internal-Token": "secret-token"},
    )
    assert ok.status_code == 200
    assert ok.json()["track"]["segmentation_metadata"]["status"] == "sam3_failed"


def test_segmentation_writeback_fails_closed_without_a_shared_token(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "internal_api_token", None)
    video_id, selected_frame_id = _seed_video()
    track_id = client.post(
        "/api/vision/track-seeds",
        json={"video_id": video_id, "frame_id": selected_frame_id, "x_ratio": 0.5, "y_ratio": 0.5},
    ).json()["track"]["id"]

    response = client.post(
        f"/api/vision/tracks/{track_id}/segmentation",
        json={"frames": []},
        headers=INTERNAL_HEADERS,
    )
    assert response.status_code == 401


def test_worker_config_with_local_frame_urls_marks_track_failed(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "sam3_worker_url", "https://worker.example/dispatch")

    video_id, selected_frame_id = _seed_video()
    response = client.post(
        "/api/vision/track-seeds",
        json={"video_id": video_id, "frame_id": selected_frame_id, "x_ratio": 0.5, "y_ratio": 0.5},
    )

    assert response.status_code == 201, response.text
    metadata = response.json()["track"]["segmentation_metadata"]
    assert metadata["status"] == "sam3_failed"
    assert "public frame storage" in metadata["error_message"]


def test_retry_rejects_a_late_writeback_from_the_prior_attempt(client, monkeypatch):
    from app.api.routes import vision
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "sam3_worker_url", "https://worker.example/dispatch")
    monkeypatch.setattr(settings, "public_media_base_url", "https://frames.example/media")
    monkeypatch.setattr(vision, "_dispatch_sam3_job", lambda *_args: None)

    video_id, selected_frame_id = _seed_video()
    seed = client.post(
        "/api/vision/track-seeds",
        json={"video_id": video_id, "frame_id": selected_frame_id, "x_ratio": 0.5, "y_ratio": 0.5},
    )
    assert seed.status_code == 201, seed.text
    track_id = seed.json()["track"]["id"]
    first_attempt = seed.json()["track"]["segmentation_metadata"]["attempt_id"]

    first_failure = client.post(
        f"/api/vision/tracks/{track_id}/segmentation",
        json={"attempt_id": first_attempt, "status": "sam3_failed", "frames": []},
        headers=INTERNAL_HEADERS,
    )
    assert first_failure.status_code == 200, first_failure.text

    retry = client.post(f"/api/vision/tracks/{track_id}/retry", json={})
    assert retry.status_code == 200, retry.text
    second_attempt = retry.json()["track"]["segmentation_metadata"]["attempt_id"]
    assert second_attempt != first_attempt

    late_result = client.post(
        f"/api/vision/tracks/{track_id}/segmentation",
        json={"attempt_id": first_attempt, "status": "sam3_failed", "frames": []},
        headers=INTERNAL_HEADERS,
    )
    assert late_result.status_code == 409


def test_empty_success_writeback_is_a_failure_and_keeps_the_click_anchor(client):
    video_id, selected_frame_id = _seed_video()
    seed = client.post(
        "/api/vision/track-seeds",
        json={"video_id": video_id, "frame_id": selected_frame_id, "x_ratio": 0.5, "y_ratio": 0.5},
    )
    track_id = seed.json()["track"]["id"]

    response = client.post(
        f"/api/vision/tracks/{track_id}/segmentation",
        json={"frames": []},
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["track"]["segmentation_metadata"]["status"] == "sam3_failed"
    assert len(body["moments"]) == 1
    assert body["moments"][0]["frame_id"] == selected_frame_id
