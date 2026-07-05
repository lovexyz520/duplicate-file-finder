from __future__ import annotations

import os
import shutil
from dataclasses import replace
from typing import Callable

from .naming import DestinationResolver, clean_filename
from .paths import path_is_within
from .types import DuplicateAction, DuplicateMatch, FileInfo

ProgressCallback = Callable[[int, int], None]


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
        original_match = path_is_within(original.path, prefer_path)
        duplicate_match = path_is_within(duplicate.path, prefer_path)
        if original_match and not duplicate_match:
            return original
        if duplicate_match and not original_match:
            return duplicate
    return original


def _send_to_trash(path: str) -> None:
    from send2trash import send2trash

    send2trash(path)


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
    to_trash: bool = False,
    progress: ProgressCallback | None = None,
) -> tuple[int, list[DuplicateAction]]:
    """處理重複檔案：移到輸出資料夾，或（to_trash=True）移到資源回收桶。

    dry_run 不會觸碰磁碟（不建資料夾、不移動）。
    個別檔案失敗會記為 action="failed" 並繼續處理其餘檔案。
    """
    if not dry_run and not to_trash:
        os.makedirs(output_folder, exist_ok=True)

    resolver = DestinationResolver()
    moved_count = 0
    operations: list[DuplicateAction] = []
    total = len(matches)

    for index, match in enumerate(matches, start=1):
        if progress:
            progress(index, total)

        keep_file = _pick_keep_file(
            match.original,
            match.duplicate,
            keep_strategy,
            prefer_path,
        )

        base_action = DuplicateAction(
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

        if keep_file.path == match.duplicate.path and move_scope != "both":
            operations.append(base_action)
            continue

        if keep_file.path == match.duplicate.path:
            src = match.original.path
        else:
            src = match.duplicate.path

        if to_trash:
            if dry_run:
                operations.append(replace(base_action, action="preview_trash"))
                continue
            try:
                _send_to_trash(src)
                moved_count += 1
                operations.append(replace(base_action, action="trashed"))
            except Exception as exc:  # noqa: BLE001 - 逐檔隔離錯誤
                operations.append(
                    replace(base_action, action="failed", error=str(exc))
                )
            continue

        filename = os.path.basename(src)
        if clean_names:
            filename = clean_filename(
                filename,
                remove_copy_suffix=clean_copy_suffix,
                normalize_space=clean_normalize_space,
                remove_special=clean_remove_special,
            )

        desired_dest, dest, name_conflict = resolver.resolve(
            output_folder,
            filename,
            conflict_suffix_width,
        )

        if dry_run:
            operations.append(
                replace(
                    base_action,
                    move_path=dest,
                    desired_move_path=desired_dest,
                    name_conflict=name_conflict,
                    action="preview",
                )
            )
            continue

        try:
            shutil.move(src, dest)
            moved_count += 1
            action = "moved"
            error = None
        except Exception as exc:  # noqa: BLE001 - 逐檔隔離錯誤
            action = "failed"
            error = str(exc)

        operations.append(
            replace(
                base_action,
                move_path=dest,
                desired_move_path=desired_dest,
                name_conflict=name_conflict,
                action=action,
                error=error,
            )
        )

    return moved_count, operations
