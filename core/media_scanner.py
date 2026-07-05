from __future__ import annotations

import os
from datetime import datetime
from typing import Callable, Mapping

from .media_types import MediaFileInfo
from .metadata import get_image_exif, get_video_metadata
from .scanner import iter_files

ProgressCallback = Callable[[int, int], None]


def _category_for_extension(ext: str, preset: Mapping[str, set[str]]) -> str:
    ext_lower = ext.lower()
    for category, exts in preset.items():
        if ext_lower in exts:
            return category
    return "OTHERS"


def scan_media_folder(
    folder: str,
    recursive: bool,
    preset: Mapping[str, set[str]],
    min_size: int = 0,
    include_hidden: bool = True,
    exclude_dirs: set[str] | None = None,
    progress: ProgressCallback | None = None,
) -> list[MediaFileInfo]:
    paths = list(iter_files(folder, recursive, include_hidden, exclude_dirs))
    total = len(paths)

    results: list[MediaFileInfo] = []
    for index, path in enumerate(paths, start=1):
        if progress:
            progress(index, total)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        if stat.st_size < min_size:
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
            shot_time = datetime.fromtimestamp(stat.st_mtime)

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
