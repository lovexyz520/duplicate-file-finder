from __future__ import annotations

import os
from typing import Callable, Iterable

from .types import FileInfo

ProgressCallback = Callable[[int, int], None]


def _is_hidden_name(name: str) -> bool:
    return name.startswith(".")


def iter_files(
    folder: str,
    recursive: bool,
    include_hidden: bool = True,
    exclude_dirs: set[str] | None = None,
) -> Iterable[str]:
    exclude = {d.lower() for d in exclude_dirs} if exclude_dirs else set()

    def _dir_ok(name: str) -> bool:
        if name.lower() in exclude:
            return False
        if not include_hidden and _is_hidden_name(name):
            return False
        return True

    def _file_ok(name: str) -> bool:
        return include_hidden or not _is_hidden_name(name)

    if recursive:
        for root, dirnames, filenames in os.walk(folder):
            dirnames[:] = [d for d in dirnames if _dir_ok(d)]
            for filename in filenames:
                if _file_ok(filename):
                    yield os.path.join(root, filename)
    else:
        for filename in os.listdir(folder):
            path = os.path.join(folder, filename)
            if os.path.isfile(path) and _file_ok(filename):
                yield path


def scan_folder(
    folder: str,
    recursive: bool = False,
    min_size: int = 0,
    include_hidden: bool = True,
    exclude_dirs: set[str] | None = None,
) -> list[FileInfo]:
    files: list[FileInfo] = []
    for path in iter_files(folder, recursive, include_hidden, exclude_dirs):
        try:
            stat = os.stat(path)
        except OSError:
            continue
        if stat.st_size < min_size:
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
