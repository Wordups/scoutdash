# Database Schema

Core entities:

- `organizations`
- `teams`
- `athletes`
- `events`
- `videos`
- `video_frames`
- `clips`
- `categories`
- `tags`
- `evidence_tags`
- `notes`
- `vision_tracks`
- `athlete_reports`

Relationships:

- Organization has many teams, athletes, events, videos, categories, and evidence tags.
- Team belongs to an organization and has many athletes, events, and videos.
- Video belongs to a team and can belong to an event.
- Video has many extracted frames used by the video intelligence workflow.
- Clip belongs to a video and supports one or more evidence tags.
- Category belongs to an organization and contains universal tag definitions.
- Evidence tag links athlete, video, timestamp, category, tag, notes, and clip.
- Vision track links video, optional athlete, frame range, bounding data, and segmentation metadata.
- Athlete report stores generated report sections, evidence tag IDs, and note IDs so every observation remains traceable.

`evidence_tags.evidence_type` is coach-authored context: `neutral`, `strength`, or `development_area`. It is not a score.

`video_frames` stores sampled FFmpeg frame outputs: frame number, timestamp, storage key, and image dimensions. `vision_tracks.bounding_data` can reference these frame IDs and store prompt boxes or future SAM3 segmentation metadata.
