# API

Base prefix: `/api`

Primary resources:

- `GET/POST /organizations`
- `GET/POST /teams`
- `GET/POST /athletes`
- `GET /athletes/{athlete_id}/profile`
- `GET/POST /events`
- `GET/POST /videos`
- `POST /videos/upload`
- `POST /videos/from-url`
- `POST /videos/{video_id}/process`
- `GET /videos/{video_id}/frames`
- `GET/POST /clips`
- `GET/POST /categories`
- `GET/POST /tags`
- `GET/POST /evidence-tags`
- `GET/POST /notes`
- `GET/POST /vision/tracks`
- `POST /vision/manual-selections`
- `POST /vision/track-seeds`
- `GET /vision/tracks/{track_id}/timeline`
- `GET/POST /athletes/{athlete_id}/reports`
- `GET /reports/{report_id}`
- `GET /reports/{report_id}/pdf`

The video intelligence workflow starts with local film upload or `POST /videos/from-url`, then `POST /videos/{video_id}/process` extracts sampled frames with FFmpeg. Coaches select an athlete on an extracted frame and call `POST /vision/track-seeds`. The response stores a SAM3-ready track seed and returns an athlete timeline. The current seed uses the coach click as the identification anchor; it does not perform coaching evaluation or behavior detection.

The evidence workflow is centered on `POST /evidence-tags`. A request links an athlete, video, timestamp, category, tag, and notes. The backend creates clip metadata automatically when no clip window is supplied.

Athlete development reports are generated from existing evidence tags and coach notes. They store section summaries plus exact evidence tag IDs, clip IDs, and note IDs. Reports do not create ratings or scores.
