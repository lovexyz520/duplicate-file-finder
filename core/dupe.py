from __future__ import annotations

from collections import defaultdict

from .hashers import full_hash, partial_hash
from .types import DuplicateMatch, FileInfo


def _index_by_size(files: list[FileInfo]) -> dict[int, list[FileInfo]]:
    size_index: dict[int, list[FileInfo]] = defaultdict(list)
    for info in files:
        size_index[info.size].append(info)
    return size_index


def find_duplicates_between(
    folder1_files: list[FileInfo],
    folder2_files: list[FileInfo],
    partial_bytes: int,
    full_hash_algo: str = "sha256",
) -> list[DuplicateMatch]:
    size_index1 = _index_by_size(folder1_files)

    candidates = [f for f in folder2_files if f.size in size_index1]
    if not candidates:
        return []

    sizes_needed = {f.size for f in candidates}

    partial_index1: dict[int, dict[str, list[FileInfo]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for info in folder1_files:
        if info.size not in sizes_needed:
            continue
        ph = partial_hash(info.path, partial_bytes)
        if ph is None:
            continue
        partial_index1[info.size][ph].append(info)

    full_cache: dict[str, str] = {}
    matches: list[DuplicateMatch] = []

    for file2 in candidates:
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
            if file1.path == file2.path:
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
) -> list[list[FileInfo]]:
    size_index = _index_by_size(files)
    duplicate_groups: list[list[FileInfo]] = []

    for size, same_size_files in size_index.items():
        if len(same_size_files) < 2:
            continue
        partial_groups: dict[str, list[FileInfo]] = defaultdict(list)
        for info in same_size_files:
            ph = partial_hash(info.path, partial_bytes)
            if ph is None:
                continue
            partial_groups[ph].append(info)

        full_cache: dict[str, str] = {}
        for partial_group in partial_groups.values():
            if len(partial_group) < 2:
                continue
            full_groups: dict[str, list[FileInfo]] = defaultdict(list)
            for info in partial_group:
                h = full_cache.get(info.path)
                if h is None:
                    h = full_hash(info.path, algo=full_hash_algo)
                    if h is None:
                        continue
                    full_cache[info.path] = h
                full_groups[h].append(info)
            for group in full_groups.values():
                if len(group) > 1:
                    duplicate_groups.append(group)

    return duplicate_groups
