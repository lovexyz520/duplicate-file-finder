from __future__ import annotations

import csv
import os

from .types import DuplicateAction, DuplicateMatch


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
            header.extend(["action", "strategy", "keep_path", "move_path"])
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
                    row.extend(["", "", "", ""])
                else:
                    row.extend(
                        [
                            action.action,
                            action.strategy,
                            action.keep_path,
                            action.move_path or "",
                        ]
                    )
            writer.writerow(row)
