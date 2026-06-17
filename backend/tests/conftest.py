import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


TEST_ROOT = Path(__file__).resolve().parent / ".tmp"
TEST_ROOT.mkdir(exist_ok=True)
TEST_DB = TEST_ROOT / f"scoutdash_{uuid4().hex}.db"
TEST_UPLOADS = TEST_ROOT / "uploads"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["LOCAL_UPLOAD_DIR"] = str(TEST_UPLOADS)
os.environ["PUBLIC_MEDIA_BASE_URL"] = "http://testserver/media"

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

