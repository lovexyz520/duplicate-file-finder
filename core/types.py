from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileInfo:
    path: str
    size: int
    mtime: float
    ctime: float
    ext: str


@dataclass(frozen=True)
class DuplicateMatch:
    original: FileInfo
    duplicate: FileInfo
    partial_hash: str
    full_hash: str


@dataclass(frozen=True)
class DuplicateAction:
    original: FileInfo
    duplicate: FileInfo
    keep_path: str
    move_path: str | None
    desired_move_path: str | None
    name_conflict: bool
    action: str
    strategy: str
    partial_hash: str
    full_hash: str
