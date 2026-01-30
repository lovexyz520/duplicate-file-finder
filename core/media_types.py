from __future__ import annotations

from dataclasses import dataclass

from .types import DuplicateAction, DuplicateMatch
from datetime import datetime


@dataclass(frozen=True)
class MediaFileInfo:
    path: str
    size: int
    mtime: float
    ctime: float
    ext: str
    category: str
    shot_time: datetime | None
    camera_model: str | None
    width: int | None
    height: int | None
    duration: float | None


@dataclass(frozen=True)
class PhotoAction:
    source_path: str
    dest_path: str
    desired_dest_path: str
    category: str
    action: str
    name_conflict: bool
    pair_key: str | None
    pair_role: str | None
    shot_date: str | None


@dataclass(frozen=True)
class PhotoPlan:
    media_files: list[MediaFileInfo]
    pairs: list[tuple[str, str, str]]  # key, jpg_path, raw_path
    orphan_jpgs: list[str]
    orphan_raws: list[str]
    duplicate_matches: list[DuplicateMatch]
    duplicate_actions: list[DuplicateAction]
    photo_actions: list[PhotoAction]
