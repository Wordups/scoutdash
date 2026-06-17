from __future__ import annotations

from typing import Any

from .contracts import AthleteTrack


def build_track_record(track: AthleteTrack) -> dict[str, Any]:
    return {
        "video_id": track.video_id,
        "athlete_id": track.athlete_id,
        "track_label": track.track_label,
        "source": track.source,
        "frame_start": track.frame_start,
        "frame_end": track.frame_end,
        "bounding_data": {
            "frames": [
                {
                    "frame_number": frame.frame_number,
                    "box": {
                        "x": frame.bounding_box.x,
                        "y": frame.bounding_box.y,
                        "width": frame.bounding_box.width,
                        "height": frame.bounding_box.height,
                    },
                }
                for frame in track.frames
            ]
        },
        "segmentation_metadata": {
            "frames": [
                {
                    "frame_number": frame.frame_number,
                    "segmentation": None
                    if frame.segmentation is None
                    else {
                        "model_name": frame.segmentation.model_name,
                        "model_version": frame.segmentation.model_version,
                        "prompt_type": frame.segmentation.prompt_type,
                        "mask_ref": frame.segmentation.mask_ref,
                        "confidence": frame.segmentation.confidence,
                        "raw": frame.segmentation.raw,
                    },
                }
                for frame in track.frames
            ]
        },
    }

