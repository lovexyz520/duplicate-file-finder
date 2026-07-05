from __future__ import annotations

import os
import shutil
from dataclasses import replace
from typing import Callable, Iterable

from .media_types import PhotoAction
from .oplog import make_record, write_oplog
from .types import DuplicateAction

ProgressCallback = Callable[[int, int], None]


def execute_photo_actions(
    actions: Iterable[PhotoAction],
    dry_run: bool,
    move: bool,
    progress: ProgressCallback | None = None,
) -> list[PhotoAction]:
    action_list = list(actions)
    total = len(action_list)
    completed: list[PhotoAction] = []
    for index, action in enumerate(action_list, start=1):
        if progress:
            progress(index, total)
        if dry_run:
            completed.append(replace(action, action="preview"))
            continue
        try:
            os.makedirs(os.path.dirname(action.dest_path), exist_ok=True)
            if move:
                shutil.move(action.source_path, action.dest_path)
                verb = "moved"
            else:
                shutil.copy2(action.source_path, action.dest_path)
                verb = "copied"
            completed.append(replace(action, action=verb))
        except Exception as exc:  # noqa: BLE001 - 逐檔隔離錯誤
            completed.append(replace(action, action="failed", error=str(exc)))
    return completed


def execute_duplicate_actions(
    actions: Iterable[DuplicateAction],
    dry_run: bool,
    progress: ProgressCallback | None = None,
) -> list[DuplicateAction]:
    action_list = list(actions)
    total = len(action_list)
    completed: list[DuplicateAction] = []
    for index, action in enumerate(action_list, start=1):
        if progress:
            progress(index, total)
        if dry_run or action.move_path is None:
            completed.append(
                replace(action, action="preview" if dry_run else action.action)
            )
            continue
        try:
            os.makedirs(os.path.dirname(action.move_path), exist_ok=True)
            shutil.move(action.duplicate.path, action.move_path)
            completed.append(replace(action, action="moved"))
        except Exception as exc:  # noqa: BLE001 - 逐檔隔離錯誤
            completed.append(replace(action, action="failed", error=str(exc)))
    return completed


def photo_actions_to_records(actions: Iterable[PhotoAction]) -> list[dict]:
    records = []
    for action in actions:
        if action.action in {"preview", "kept_by_strategy"}:
            continue
        op = "move" if action.action in {"moved", "failed"} else "copy"
        if action.action == "copied":
            op = "copy"
        records.append(
            make_record(
                op=op,
                source=action.source_path,
                dest=action.dest_path,
                status=action.action,
                kind="photo",
                error=action.error,
                category=action.category,
                pair_key=action.pair_key,
                pair_role=action.pair_role,
                shot_date=action.shot_date,
                name_conflict=action.name_conflict,
            )
        )
    return records


def duplicate_actions_to_records(actions: Iterable[DuplicateAction]) -> list[dict]:
    records = []
    for action in actions:
        if action.action in {"preview", "preview_trash", "kept_by_strategy"}:
            continue
        op = "trash" if action.action == "trashed" else "move"
        records.append(
            make_record(
                op=op,
                source=action.duplicate.path,
                dest=action.move_path,
                status=action.action,
                kind="duplicate",
                error=action.error,
                keep_path=action.keep_path,
                strategy=action.strategy,
                full_hash=action.full_hash,
                name_conflict=action.name_conflict,
            )
        )
    return records


def write_actions_log(
    actions: Iterable[PhotoAction],
    duplicate_actions: Iterable[DuplicateAction],
    log_path: str,
) -> None:
    records = photo_actions_to_records(actions) + duplicate_actions_to_records(
        duplicate_actions
    )
    write_oplog(records, log_path)
