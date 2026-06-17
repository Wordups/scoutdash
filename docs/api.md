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
- `GET/POST /clips`
- `GET/POST /categories`
- `GET/POST /tags`
- `GET/POST /evidence-tags`
- `GET/POST /notes`
- `GET/POST /vision/tracks`
- `POST /vision/manual-selections`

The evidence workflow is centered on `POST /evidence-tags`. A request links an athlete, video, timestamp, category, tag, and notes. The backend creates clip metadata automatically when no clip window is supplied.

