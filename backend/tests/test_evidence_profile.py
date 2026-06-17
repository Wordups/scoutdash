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

