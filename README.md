# ScoutDash

ScoutDash is a sports development intelligence platform for organizing game film around athlete identification, athlete timelines, and coach-reviewed evidence.

The current product foundation is the Video Intelligence Engine: upload or import film, extract frames, select the athlete, create a SAM3-ready player track, review that athlete's timeline, and turn moments into evidence tags. SAM3 is the identification layer only. Coaches validate, and ScoutDash stores evidence.

## Stack

- Frontend: Next.js, TypeScript, Tailwind
- Backend: FastAPI, SQLAlchemy
- Database: PostgreSQL in Docker, SQLite fallback for quick local backend runs
- Video: FFmpeg frame extraction with a packaged binary fallback; FFprobe is optional
- Storage: local or S3-compatible persistent video and frame storage
- Vision: SAM3-ready module at `services/vision`

## Local Development

```bash
cd scoutdash
docker compose up --build
```

Then open:

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Processing diagnostics: http://localhost:8000/health/capabilities

For backend-only development:

```bash
cd scoutdash/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The Python dependencies include a portable FFmpeg executable, so backend-only development and
Northflank builds do not require a separate machine-level FFmpeg installation. A configured
`FFMPEG_BINARY` still takes precedence, followed by a system installation.

## Production Film Storage

Production must use either a persistent volume with `STORAGE_BACKEND=local` or S3-compatible
object storage. S3 is recommended because uploaded film and generated review frames survive
service redeploys. Configure:

```env
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=<private S3 endpoint, or omit for AWS>
S3_PUBLIC_ENDPOINT_URL=<browser-reachable S3 endpoint>
S3_BUCKET=scoutdash-film
S3_ACCESS_KEY_ID=<access key>
S3_SECRET_ACCESS_KEY=<secret key>
S3_REGION=us-east-1
```

The bucket must exist and allow browser CORS reads from the ScoutDash frontend. Docker Compose
creates the local MinIO bucket automatically. `/health/capabilities` reports whether storage and
video processing are configured before a coach uploads film.

For a Northflank persistent volume instead of S3, mount the volume at a stable path such as
`/data/scoutdash-film` and configure:

```env
STORAGE_BACKEND=local
LOCAL_UPLOAD_DIR=/data/scoutdash-film
LOCAL_STORAGE_PERSISTENT=true
PUBLIC_MEDIA_BASE_URL=https://YOUR-BACKEND-URL/media
```

Without either S3 or a mounted persistent volume, Northflank's service filesystem can be replaced
during deployment and uploaded film will need to be uploaded again.

## Current Scope

- organizations, teams, athletes, events
- film uploads, direct URL imports, and video review
- FFmpeg frame extraction
- coach-click player track seeds for future SAM3 segmentation and tracking
- athlete timeline review from stored track metadata
- universal categories and tags
- timestamped behavior evidence
- athlete profiles with strengths, development areas, frequency, consistency, clips, and coach notes
- athlete development reports generated from traceable evidence and notes

No automatic behavior detection, player ratings, or coaching recommendations are included.

