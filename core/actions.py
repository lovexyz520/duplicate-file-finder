from __future__ import annotations

import os
import shutil

from .naming import clean_filename, resolve_destination
from .types import DuplicateAction, DuplicateMatch, FileInfo


def _path_matches(path: str, prefer_path: str) -> bool:
    normalized = os.path.abspath(path)
    prefer_normalized = os.path.abspath(prefer_path)
    if normalized == prefer_normalized:
        return True
    with_sep = prefer_normalized + os.sep
    return normalized.startswith(with_sep)


def _pick_keep_file(
    original: FileInfo,
    duplicate: FileInfo,
    strategy: str,
    prefer_path: str | None,
) -> FileInfo:
    if strategy == "folder1":
        return original
    if strategy == "folder2":
        return duplicate
    if strategy == "latest":
        return original if original.mtime >= duplicate.mtime else duplicate
    if strategy == "earliest":
        return original if original.ctime <= duplicate.ctime else duplicate
    if strategy == "prefer-path" and prefer_path:
        original_match = _path_matches(original.path, prefer_path)
        duplicate_match = _path_matches(duplicate.path, prefer_path)
        if original_match and not duplicate_match:
            return original
        if duplicate_match and not original_match:
            return duplicate
    return original


def _clean_filename(
    filename: str,
    remove_copy_suffix: bool,
    normalize_space: bool,
    remove_special: bool,
) -> str:
    return clean_filename(filename, remove_copy_suffix, normalize_space, remove_special)


def move_duplicates(
    matches: list[DuplicateMatch],
    output_folder: str,
    dry_run: bool = False,
    keep_strategy: str = "folder1",
    prefer_path: str | None = None,
    move_scope: str = "folder2",
    clean_names: bool = False,
    clean_copy_suffix: bool = False,
    clean_normalize_space: bool = False,
    clean_remove_special: bool = False,
    conflict_suffix_width: int = 3,
) -> tuple[int, list[DuplicateAction]]:
    os.makedirs(output_folder, exist_ok=True)

    moved_count = 0
    operations: list[DuplicateAction] = []

    for match in matches:
        keep_file = _pick_keep_file(
            match.original,
            match.duplicate,
            keep_strategy,
            prefer_path,
        )

        if keep_file.path == match.duplicate.path and move_scope != "both":
            operations.append(
                DuplicateAction(
                    original=match.original,
                    duplicate=match.duplicate,
                    keep_path=keep_file.path,
                    move_path=None,
                    desired_move_path=None,
                    name_conflict=False,
                    action="kept_by_strategy",
                    strategy=keep_strategy,
                    partial_hash=match.partial_hash,
                    full_hash=match.full_hash,
                )
            )
            continue

        if keep_file.path == match.duplicate.path:
            src = match.original.path
        else:
            src = match.duplicate.path

        filename = os.path.basename(src)
        if clean_names:
            filename = _clean_filename(
                filename,
                remove_copy_suffix=clean_copy_suffix,
                normalize_space=clean_normalize_space,
                remove_special=clean_remove_special,
            )

        desired_dest, dest, name_conflict = resolve_destination(
            output_folder,
            filename,
            conflict_suffix_width,
        )

        if dry_run:
            action = "preview"
        else:
            shutil.move(src, dest)
            moved_count += 1
            action = "moved"

        operations.append(
            DuplicateAction(
                original=match.original,
                duplicate=match.duplicate,
                keep_path=keep_file.path,
                move_path=dest,
                desired_move_path=desired_dest,
                name_conflict=name_conflict,
                action=action,
                strategy=keep_strategy,
                partial_hash=match.partial_hash,
                full_hash=match.full_hash,
            )
        )

    return moved_count, operations
