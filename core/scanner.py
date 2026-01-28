from __future__ import annotations

import os
from typing import Iterable

from .types import FileInfo


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


def scan_folder(folder: str, recursive: bool = False) -> list[FileInfo]:
    files: list[FileInfo] = []
    for path in _iter_files(folder, recursive):
        try:
            stat = os.stat(path)
        except OSError:
            continue
        _, ext = os.path.splitext(path)
        files.append(
            FileInfo(
                path=path,
                size=stat.st_size,
                mtime=stat.st_mtime,
                ctime=stat.st_ctime,
                ext=ext.lower(),
            )
        )
    return files
