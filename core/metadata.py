from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    import exifread  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    exifread = None

try:
    from hachoir.metadata import extractMetadata  # type: ignore
    from hachoir.parser import createParser  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    extractMetadata = None
    createParser = None


def _parse_exif_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value)
    try:
        # EXIF standard: "YYYY:MM:DD HH:MM:SS"
        return datetime.strptime(text, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def get_image_exif(path: str) -> tuple[datetime | None, str | None]:
    if exifread is None:
        return None, None
    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False, strict=True)
        shot = (
            _parse_exif_datetime(tags.get("EXIF DateTimeOriginal"))
            or _parse_exif_datetime(tags.get("EXIF DateTimeDigitized"))
            or _parse_exif_datetime(tags.get("Image DateTime"))
        )
        model = tags.get("Image Model")
        camera_model = str(model) if model is not None else None
        return shot, camera_model
    except Exception:
        return None, None


def _hachoir_to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def get_video_metadata(path: str) -> dict[str, Any]:
    if createParser is None or extractMetadata is None:
        return {}
    try:
        parser = createParser(path)
        if parser is None:
            return {}
        metadata = extractMetadata(parser)
        if metadata is None:
            return {}
        shot_time = _hachoir_to_datetime(metadata.get("creation_date"))
        if shot_time is None:
            shot_time = _hachoir_to_datetime(metadata.get("date"))
        duration = metadata.get("duration")
        width = metadata.get("width")
        height = metadata.get("height")
        result = {}
        if shot_time:
            # Normalize to naive local time for consistency with file mtime
            if shot_time.tzinfo is not None:
                shot_time = shot_time.astimezone(timezone.utc).replace(tzinfo=None)
            result["shot_time"] = shot_time
        if duration:
            result["duration"] = float(duration.total_seconds())
        if width:
            result["width"] = int(width)
        if height:
            result["height"] = int(height)
        return result
    except Exception:
        return {}
