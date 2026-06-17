# Database Schema

Core entities:

- `organizations`
- `teams`
- `athletes`
- `events`
- `videos`
- `clips`
- `categories`
- `tags`
- `evidence_tags`
- `notes`
- `vision_tracks`

Relationships:

- Organization has many teams, athletes, events, videos, categories, and evidence tags.
- Team belongs to an organization and has many athletes, events, and videos.
- Video belongs to a team and can belong to an event.
- Clip belongs to a video and supports one or more evidence tags.
- Category belongs to an organization and contains universal tag definitions.
- Evidence tag links athlete, video, timestamp, category, tag, notes, and clip.
- Vision track links video, optional athlete, frame range, bounding data, and segmentation metadata.

`evidence_tags.evidence_type` is coach-authored context: `neutral`, `strength`, or `development_area`. It is not a score.

