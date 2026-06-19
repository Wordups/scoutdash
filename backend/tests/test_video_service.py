from pathlib import Path

from app.services.film_metadata import capabilities, ensure_binaries


def test_static_ffmpeg_supplies_both_processing_binaries():
    ffmpeg, ffprobe = ensure_binaries()
    result = capabilities()

    assert Path(ffmpeg).is_file()
    assert Path(ffprobe).is_file()
    assert result["ready"] is True
    assert result["ffmpeg"] == ffmpeg
    assert result["ffprobe"] == ffprobe
    assert result["error"] is None
