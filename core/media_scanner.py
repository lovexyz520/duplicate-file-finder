from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable, Mapping

from .media_types import MediaFileInfo
from .metadata import get_image_exif, get_video_metadata


def _iter_files(folder: str, recursive: bool) -> Iterable[str]:
    if recursive:
        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                yield os.path.join(root, filename)
    else:
        for filename in os.listdir(folder):
            path = os.path.join(folder, filename)
            if os.path.isfile(path):
                yield path


def _category_for_extension(ext: str, preset: Mapping[str, set[str]]) -> str:
    ext_lower = ext.lower()
    for category, exts in preset.items():
        if ext_lower in exts:
            return category
    return "OTHERS"


def _shot_time_from_mtime(mtime: float) -> datetime:
    return datetime.fromtimestamp(mtime)


def scan_media_folder(
    folder: str,
    recursive: bool,
    preset: Mapping[str, set[str]],
) -> list[MediaFileInfo]:
    results: list[MediaFileInfo] = []
    for path in _iter_files(folder, recursive):
        try:
            stat = os.stat(path)
        except OSError:
            continue
        _, ext = os.path.splitext(path)
        category = _category_for_extension(ext, preset)

        shot_time = None
        camera_model = None
        width = None
        height = None
        duration = None

        if category in {"RAW", "JPG"}:
            shot_time, camera_model = get_image_exif(path)
        elif category == "VIDEO":
            meta = get_video_metadata(path)
            shot_time = meta.get("shot_time")
            duration = meta.get("duration")
            width = meta.get("width")
            height = meta.get("height")

        if shot_time is None:
            shot_time = _shot_time_from_mtime(stat.st_mtime)

        results.append(
            MediaFileInfo(
                path=path,
                size=stat.st_size,
                mtime=stat.st_mtime,
                ctime=stat.st_ctime,
                ext=ext.lower(),
                category=category,
                shot_time=shot_time,
                camera_model=camera_model,
                width=width,
                height=height,
                duration=duration,
            )
        )
    return results
