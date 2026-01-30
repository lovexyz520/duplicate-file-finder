from __future__ import annotations

import csv
import os

from .types import DuplicateAction, DuplicateMatch
from .types import OrganizeAction
from .pairing import PairRecord


def write_duplicates_report(
    matches: list[DuplicateMatch],
    report_path: str,
    actions: list[DuplicateAction] | None = None,
) -> None:
    report_dir = os.path.dirname(report_path)
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)

    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "duplicate_path",
            "original_path",
            "size",
            "mtime_duplicate",
            "mtime_original",
            "ctime_duplicate",
            "ctime_original",
            "partial_hash",
            "full_hash",
        ]
        if actions is not None:
            header.extend(
                [
                    "action",
                    "strategy",
                    "keep_path",
                    "move_path",
                    "desired_move_path",
                    "name_conflict",
                ]
            )
        writer.writerow(header)

        action_map = {}
        if actions is not None:
            action_map = {
                (a.original.path, a.duplicate.path): a for a in actions
            }

        for match in matches:
            row = [
                match.duplicate.path,
                match.original.path,
                match.duplicate.size,
                match.duplicate.mtime,
                match.original.mtime,
                match.duplicate.ctime,
                match.original.ctime,
                match.partial_hash,
                match.full_hash,
            ]
            if actions is not None:
                action = action_map.get((match.original.path, match.duplicate.path))
                if action is None:
                    row.extend(["", "", "", "", "", ""])
                else:
                    row.extend(
                        [
                            action.action,
                            action.strategy,
                            action.keep_path,
                            action.move_path or "",
                            action.desired_move_path or "",
                            "1" if action.name_conflict else "0",
                        ]
                    )
            writer.writerow(row)


def write_organize_report(actions: list[OrganizeAction], report_path: str) -> None:
    report_dir = os.path.dirname(report_path)
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)

    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "source_path",
                "dest_path",
                "desired_dest_path",
                "category",
                "action",
                "name_conflict",
            ]
        )
        for action in actions:
            writer.writerow(
                [
                    action.source_path,
                    action.dest_path,
                    action.desired_dest_path,
                    action.category,
                    action.action,
                    "1" if action.name_conflict else "0",
                ]
            )


def write_pairs_report(
    pairs: list[PairRecord],
    orphans_jpg: list[str],
    orphans_raw: list[str],
    pairs_path: str,
    orphans_path: str,
) -> None:
    pairs_dir = os.path.dirname(pairs_path)
    if pairs_dir:
        os.makedirs(pairs_dir, exist_ok=True)

    with open(pairs_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["key", "jpg_path", "raw_path"])
        for pair in pairs:
            writer.writerow([pair.key, pair.jpg_path, pair.raw_path])

    orphans_dir = os.path.dirname(orphans_path)
    if orphans_dir:
        os.makedirs(orphans_dir, exist_ok=True)

    with open(orphans_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["type", "path"])
        for path in orphans_jpg:
            writer.writerow(["jpg", path])
        for path in orphans_raw:
            writer.writerow(["raw", path])
