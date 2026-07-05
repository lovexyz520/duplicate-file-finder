from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from .hashers import full_hash, partial_hash
from .paths import path_is_within
from .types import DuplicateMatch, FileInfo

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class GroupedFile:
    info: FileInfo
    partial_hash: str
    full_hash: str


def _index_by_size(files: list[FileInfo]) -> dict[int, list[FileInfo]]:
    size_index: dict[int, list[FileInfo]] = defaultdict(list)
    for info in files:
        size_index[info.size].append(info)
    return size_index


def pick_keep_for_group(
    group: list[FileInfo],
    strategy: str,
    prefer_path: str | None,
) -> FileInfo:
    if strategy == "latest":
        return max(group, key=lambda f: f.mtime)
    if strategy == "earliest":
        return min(group, key=lambda f: f.ctime)
    if strategy == "prefer-path" and prefer_path:
        for info in group:
            if path_is_within(info.path, prefer_path):
                return info
    return group[0]


def find_duplicates_between(
    folder1_files: list[FileInfo],
    folder2_files: list[FileInfo],
    partial_bytes: int,
    full_hash_algo: str = "sha256",
    progress: ProgressCallback | None = None,
) -> list[DuplicateMatch]:
    size_index1 = _index_by_size(folder1_files)

    candidates = [f for f in folder2_files if f.size in size_index1]
    if not candidates:
        return []

    sizes_needed = {f.size for f in candidates}

    partial_index1: dict[int, dict[str, list[FileInfo]]] = defaultdict(
        lambda: defaultdict(list)
    )
    files1_needed = [f for f in folder1_files if f.size in sizes_needed]
    total = len(files1_needed) + len(candidates)
    done = 0
    for info in files1_needed:
        ph = partial_hash(info.path, partial_bytes)
        done += 1
        if progress:
            progress(done, total)
        if ph is None:
            continue
        partial_index1[info.size][ph].append(info)

    full_cache: dict[str, str] = {}
    matches: list[DuplicateMatch] = []

    for file2 in candidates:
        done += 1
        if progress:
            progress(done, total)
        ph2 = partial_hash(file2.path, partial_bytes)
        if ph2 is None:
            continue
        matching_files1 = partial_index1[file2.size].get(ph2, [])
        if not matching_files1:
            continue

        h2 = full_cache.get(file2.path)
        if h2 is None:
            h2 = full_hash(file2.path, algo=full_hash_algo)
            if h2 is None:
                continue
            full_cache[file2.path] = h2

        for file1 in matching_files1:
            if os.path.normcase(os.path.abspath(file1.path)) == os.path.normcase(
                os.path.abspath(file2.path)
            ):
                continue
            h1 = full_cache.get(file1.path)
            if h1 is None:
                h1 = full_hash(file1.path, algo=full_hash_algo)
                if h1 is None:
                    continue
                full_cache[file1.path] = h1

            if h1 == h2:
                matches.append(
                    DuplicateMatch(
                        original=file1,
                        duplicate=file2,
                        partial_hash=ph2,
                        full_hash=h2,
                    )
                )
                break

    return matches


def group_duplicates(
    files: list[FileInfo],
    partial_bytes: int,
    full_hash_algo: str = "sha256",
    progress: ProgressCallback | None = None,
) -> list[list[GroupedFile]]:
    """單一集合內的重複分群，回傳每檔已算好的 hash 供呼叫端重用。"""
    size_index = _index_by_size(files)

    pending = [g for g in size_index.values() if len(g) >= 2]
    total = sum(len(g) for g in pending)
    done = 0

    duplicate_groups: list[list[GroupedFile]] = []

    for same_size_files in pending:
        partial_groups: dict[str, list[tuple[FileInfo, str]]] = defaultdict(list)
        for info in same_size_files:
            ph = partial_hash(info.path, partial_bytes)
            done += 1
            if progress:
                progress(done, total)
            if ph is None:
                continue
            partial_groups[ph].append((info, ph))

        for partial_group in partial_groups.values():
            if len(partial_group) < 2:
                continue
            full_groups: dict[str, list[GroupedFile]] = defaultdict(list)
            for info, ph in partial_group:
                fh = full_hash(info.path, algo=full_hash_algo)
                if fh is None:
                    continue
                full_groups[fh].append(
                    GroupedFile(info=info, partial_hash=ph, full_hash=fh)
                )
            for group in full_groups.values():
                if len(group) > 1:
                    duplicate_groups.append(group)

    return duplicate_groups
