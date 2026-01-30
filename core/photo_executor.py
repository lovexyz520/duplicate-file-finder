from __future__ import annotations

import json
import os
import shutil
from typing import Iterable

from .media_types import PhotoAction
from .types import DuplicateAction


def execute_photo_actions(
    actions: Iterable[PhotoAction],
    dry_run: bool,
    move: bool,
) -> list[PhotoAction]:
    completed: list[PhotoAction] = []
    for action in actions:
        if dry_run:
            completed.append(
                PhotoAction(
                    source_path=action.source_path,
                    dest_path=action.dest_path,
                    desired_dest_path=action.desired_dest_path,
                    category=action.category,
                    action="preview",
                    name_conflict=action.name_conflict,
                    pair_key=action.pair_key,
                    pair_role=action.pair_role,
                    shot_date=action.shot_date,
                )
            )
            continue
        os.makedirs(os.path.dirname(action.dest_path), exist_ok=True)
        if move:
            shutil.move(action.source_path, action.dest_path)
            verb = "moved"
        else:
            shutil.copy2(action.source_path, action.dest_path)
            verb = "copied"
        completed.append(
            PhotoAction(
                source_path=action.source_path,
                dest_path=action.dest_path,
                desired_dest_path=action.desired_dest_path,
                category=action.category,
                action=verb,
                name_conflict=action.name_conflict,
                pair_key=action.pair_key,
                pair_role=action.pair_role,
                shot_date=action.shot_date,
            )
        )
    return completed


def execute_duplicate_actions(
    actions: Iterable[DuplicateAction],
    dry_run: bool,
) -> list[DuplicateAction]:
    completed: list[DuplicateAction] = []
    for action in actions:
        if dry_run or action.move_path is None:
            completed.append(
                DuplicateAction(
                    original=action.original,
                    duplicate=action.duplicate,
                    keep_path=action.keep_path,
                    move_path=action.move_path,
                    desired_move_path=action.desired_move_path,
                    name_conflict=action.name_conflict,
                    action="preview" if dry_run else action.action,
                    strategy=action.strategy,
                    partial_hash=action.partial_hash,
                    full_hash=action.full_hash,
                )
            )
            continue
        os.makedirs(os.path.dirname(action.move_path), exist_ok=True)
        shutil.move(action.duplicate.path, action.move_path)
        completed.append(
            DuplicateAction(
                original=action.original,
                duplicate=action.duplicate,
                keep_path=action.keep_path,
                move_path=action.move_path,
                desired_move_path=action.desired_move_path,
                name_conflict=action.name_conflict,
                action="moved",
                strategy=action.strategy,
                partial_hash=action.partial_hash,
                full_hash=action.full_hash,
            )
        )
    return completed


def write_actions_log(
    actions: Iterable[PhotoAction],
    duplicate_actions: Iterable[DuplicateAction],
    log_path: str,
) -> None:
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        for action in actions:
            record = {
                "type": "photo",
                "source_path": action.source_path,
                "dest_path": action.dest_path,
                "desired_dest_path": action.desired_dest_path,
                "category": action.category,
                "action": action.action,
                "name_conflict": action.name_conflict,
                "pair_key": action.pair_key,
                "pair_role": action.pair_role,
                "shot_date": action.shot_date,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        for action in duplicate_actions:
            record = {
                "type": "duplicate",
                "duplicate_path": action.duplicate.path,
                "original_path": action.original.path,
                "keep_path": action.keep_path,
                "move_path": action.move_path,
                "desired_move_path": action.desired_move_path,
                "action": action.action,
                "strategy": action.strategy,
                "name_conflict": action.name_conflict,
                "partial_hash": action.partial_hash,
                "full_hash": action.full_hash,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
