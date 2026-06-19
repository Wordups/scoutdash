import subprocess


def _post(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code < 400, response.text
    return response.json()


def test_evidence_tags_build_athlete_profile(client):
    org = _post(client, "/api/organizations", {"name": "Club One", "sport_label": "Multi-sport"})
    team = _post(
        client,
        "/api/teams",
        {"organization_id": org["id"], "name": "Varsity", "sport": "Basketball", "season": "2026"},
    )
    athlete = _post(
        client,
        "/api/athletes",
        {
            "organization_id": org["id"],
            "team_id": team["id"],
            "display_name": "Bella",
            "jersey_number": "12",
            "position": "Guard",
        },
    )
    event = _post(
        client,
        "/api/events",
        {"organization_id": org["id"], "team_id": team["id"], "name": "Game 1", "sport": "Basketball"},
    )
    video = _post(
        client,
        "/api/videos",
        {
            "organization_id": org["id"],
            "team_id": team["id"],
            "event_id": event["id"],
            "title": "Game Film",
            "storage_key": "manual/game-film.mp4",
        },
    )
    category = _post(
        client,
        "/api/categories",
        {"organization_id": org["id"], "sport": "Basketball", "name": "Defense"},
    )
    tag = _post(client, "/api/tags", {"category_id": category["id"], "name": "Help Rotation"})

    _post(
        client,
        "/api/evidence-tags",
        {
            "organization_id": org["id"],
            "team_id": team["id"],
            "athlete_id": athlete["id"],
            "event_id": event["id"],
            "video_id": video["id"],
            "category_id": category["id"],
            "tag_id": tag["id"],
            "timestamp_seconds": 42.5,
            "evidence_type": "strength",
            "notes": "Early weak-side help.",
        },
    )
    _post(
        client,
        "/api/evidence-tags",
        {
            "organization_id": org["id"],
            "team_id": team["id"],
            "athlete_id": athlete["id"],
            "event_id": event["id"],
            "video_id": video["id"],
            "category_id": category["id"],
            "tag_id": tag["id"],
            "timestamp_seconds": 85.0,
            "evidence_type": "neutral",
            "notes": "Recognized the drive.",
        },
    )
    _post(
        client,
        "/api/notes",
        {"organization_id": org["id"], "athlete_id": athlete["id"], "body": "Ask about communication cues."},
    )

    profile_response = client.get(f"/api/athletes/{athlete['id']}/profile")
    assert profile_response.status_code == 200
    profile = profile_response.json()

    assert profile["athlete"]["display_name"] == "Bella"
    assert profile["behavior_frequency"][0]["tag_name"] == "Help Rotation"
    assert profile["behavior_frequency"][0]["evidence_count"] == 2
    assert profile["behavior_frequency"][0]["video_count"] == 1
    assert profile["behavior_frequency"][0]["event_count"] == 1
    assert profile["strengths"][0]["evidence_count"] == 1
    assert len(profile["evidence_clips"]) == 2
    assert profile["coach_notes"][0]["body"] == "Ask about communication cues."


def test_generates_traceable_athlete_development_report_and_pdf(client):
    org = _post(client, "/api/organizations", {"name": "Club One", "sport_label": "Multi-sport"})
    team = _post(
        client,
        "/api/teams",
        {"organization_id": org["id"], "name": "Varsity", "sport": "Basketball", "season": "2026"},
    )
    athlete = _post(
        client,
        "/api/athletes",
        {
            "organization_id": org["id"],
            "team_id": team["id"],
            "display_name": "Bella",
            "jersey_number": "12",
            "position": "Guard",
        },
    )
    event = _post(
        client,
        "/api/events",
        {"organization_id": org["id"], "team_id": team["id"], "name": "Game 1", "sport": "Basketball"},
    )
    video = _post(
        client,
        "/api/videos",
        {
            "organization_id": org["id"],
            "team_id": team["id"],
            "event_id": event["id"],
            "title": "Game Film",
            "storage_key": "manual/game-film.mp4",
        },
    )
    category = _post(
        client,
        "/api/categories",
        {"organization_id": org["id"], "sport": "Basketball", "name": "Defense"},
    )
    help_rotation = _post(client, "/api/tags", {"category_id": category["id"], "name": "Help Rotation"})
    box_out = _post(client, "/api/tags", {"category_id": category["id"], "name": "Box Out"})

    strength_tag = _post(
        client,
        "/api/evidence-tags",
        {
            "organization_id": org["id"],
            "team_id": team["id"],
            "athlete_id": athlete["id"],
            "event_id": event["id"],
            "video_id": video["id"],
            "category_id": category["id"],
            "tag_id": help_rotation["id"],
            "timestamp_seconds": 42.5,
            "evidence_type": "strength",
            "notes": "Early weak-side help.",
        },
    )
    development_tag = _post(
        client,
        "/api/evidence-tags",
        {
            "organization_id": org["id"],
            "team_id": team["id"],
            "athlete_id": athlete["id"],
            "event_id": event["id"],
            "video_id": video["id"],
            "category_id": category["id"],
            "tag_id": box_out["id"],
            "timestamp_seconds": 85.0,
            "evidence_type": "development_area",
            "notes": "Late body contact on the rebound.",
        },
    )
    note = _post(
        client,
        "/api/notes",
        {"organization_id": org["id"], "athlete_id": athlete["id"], "body": "Ask about communication cues."},
    )

    report = _post(client, f"/api/athletes/{athlete['id']}/reports", {"generated_by": "Coach"})

    assert report["title"] == "Bella Athlete Development Report"
    assert set(report["evidence_tag_ids"]) == {development_tag["id"], strength_tag["id"]}
    assert report["note_ids"] == [note["id"]]
    assert report["report_data"]["evidence_count"] == 2
    assert report["report_data"]["note_count"] == 1

    sections = {section["key"]: section for section in report["report_data"]["sections"]}
    assert "Athlete Information" == sections["athlete_information"]["title"]
    assert sections["strengths"]["supporting_evidence"][0]["evidence_tag_id"] == strength_tag["id"]
    assert sections["development_areas"]["supporting_evidence"][0]["evidence_tag_id"] == development_tag["id"]
    assert sections["coach_notes"]["supporting_notes"][0]["note_id"] == note["id"]
    assert sections["supporting_evidence"]["supporting_evidence"][0]["clip_id"] is not None

    serialized = str(report).lower()
    assert "rating" not in serialized
    assert "score" not in serialized

    list_response = client.get(f"/api/athletes/{athlete['id']}/reports")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == report["id"]

    pdf_response = client.get(f"/api/reports/{report['id']}/pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF")


def test_video_processing_and_player_track_seed_workflow(client, tmp_path):
    from app.core.config import get_settings
    from app.services.video import resolve_ffmpeg

    capability_response = client.get("/health/capabilities")
    assert capability_response.status_code == 200
    processing_capabilities = capability_response.json()["video_processing"]
    assert processing_capabilities["ready"] is True
    assert processing_capabilities["ffprobe"]

    source_video = tmp_path / "game-film.mp4"
    subprocess.run(
        [
            resolve_ffmpeg(get_settings()),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=10:duration=2",
            "-metadata",
            "creation_time=2026-06-19T01:02:03Z",
            "-pix_fmt",
            "yuv420p",
            str(source_video),
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )

    org = _post(client, "/api/organizations", {"name": "Club One", "sport_label": "Multi-sport"})
    team = _post(
        client,
        "/api/teams",
        {"organization_id": org["id"], "name": "Varsity", "sport": "Basketball", "season": "2026"},
    )
    athlete = _post(
        client,
        "/api/athletes",
        {
            "organization_id": org["id"],
            "team_id": team["id"],
            "display_name": "Player #3",
            "jersey_number": "3",
        },
    )

    with source_video.open("rb") as file_handle:
        upload_response = client.post(
            "/api/videos/upload",
            data={"organization_id": org["id"], "team_id": team["id"], "title": "Game Film"},
            files={"file": ("game-film.mp4", file_handle, "video/mp4")},
        )
    assert upload_response.status_code == 201, upload_response.text
    video = upload_response.json()
    assert video["duration_seconds"] == 2.0
    assert video["fps"] == 10.0
    assert video["frame_count"] == 20
    assert video["width"] == 320
    assert video["height"] == 240
    assert video["codec"]
    assert video["creation_time"].startswith("2026-06-19T01:02:03")

    readiness_response = client.get(f"/api/videos/{video['id']}/readiness")
    assert readiness_response.status_code == 200, readiness_response.text
    assert readiness_response.json()["file_available"] is True
    assert readiness_response.json()["processing_ready"] is True

    process_response = client.post(
        f"/api/videos/{video['id']}/process",
        json={"sample_fps": 1, "max_frames": 4},
    )
    assert process_response.status_code == 202, process_response.text
    queued_job = process_response.json()
    assert queued_job["video_id"] == video["id"]

    status_response = client.get(f"/api/videos/{video['id']}/process-status")
    assert status_response.status_code == 200, status_response.text
    completed_job = status_response.json()
    assert completed_job["status"] == "completed", completed_job
    assert completed_job["frame_count_extracted"] >= 2

    processed_frames = client.get(f"/api/videos/{video['id']}/frames").json()
    first_frame = processed_frames[0]
    assert first_frame["storage_key"].startswith(f"frames/{video['id']}/")

    processed_readiness = client.get(f"/api/videos/{video['id']}/readiness").json()
    assert processed_readiness["extracted_frame_count"] == completed_job["frame_count_extracted"]
    assert "review moments" in processed_readiness["message"]
    assert first_frame["frame_url"].endswith(".jpg")

    track_response = client.post(
        "/api/vision/track-seeds",
        json={
            "video_id": video["id"],
            "athlete_id": athlete["id"],
            "frame_id": first_frame["id"],
            "x_ratio": 0.5,
            "y_ratio": 0.5,
            "track_label": "Player #3",
        },
    )
    assert track_response.status_code == 201, track_response.text
    timeline = track_response.json()
    assert timeline["track"]["status"] == "track_seed"
    assert timeline["track"]["source"] == "coach_click_sam3_seed"
    assert timeline["track"]["segmentation_metadata"]["status"] == "sam3_adapter_not_configured"
    assert timeline["athlete"]["display_name"] == "Player #3"
    assert len(timeline["moments"]) == completed_job["frame_count_extracted"]

    timeline_response = client.get(f"/api/vision/tracks/{timeline['track']['id']}/timeline")
    assert timeline_response.status_code == 200
    assert timeline_response.json()["moments"][0]["frame_id"] == first_frame["id"]

    stored_video_path = get_settings().local_upload_dir / video["storage_key"]
    stored_video_path.unlink()
    missing_response = client.post(
        f"/api/videos/{video['id']}/process",
        json={"sample_fps": 1, "max_frames": 4},
    )
    assert missing_response.status_code == 404
    assert "Upload the film again" in missing_response.json()["detail"]

    preserved_frames = client.get(f"/api/videos/{video['id']}/frames").json()
    assert [frame["id"] for frame in preserved_frames] == [frame["id"] for frame in processed_frames]
