from pathlib import Path

from app.core.config import Settings
from app.services import video


def test_packaged_ffmpeg_is_used_when_system_binary_is_missing(monkeypatch):
    monkeypatch.setattr(video.shutil, "which", lambda _: None)
    settings = Settings(ffmpeg_binary=None, ffprobe_binary=None)

    assert Path(video.resolve_ffmpeg(settings)).is_file()
    assert video.processing_capabilities(settings)["ready"] is True
