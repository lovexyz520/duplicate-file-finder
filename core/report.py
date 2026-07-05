from __future__ import annotations

import csv
import io
import os

from .types import DuplicateAction, DuplicateMatch
from .types import OrganizeAction
from .pairing import PairRecord


def duplicates_report_csv(
    matches: list[DuplicateMatch],
    actions: list[DuplicateAction] | None = None,
) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
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
                "error",
            ]
        )
    writer.writerow(header)

    action_map = {}
    if actions is not None:
        action_map = {(a.original.path, a.duplicate.path): a for a in actions}

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
                row.extend(["", "", "", "", "", "", ""])
            else:
                row.extend(
                    [
                        action.action,
                        action.strategy,
                        action.keep_path,
                        action.move_path or "",
                        action.desired_move_path or "",
                        "1" if action.name_conflict else "0",
                        action.error or "",
                    ]
                )
        writer.writerow(row)
    return buf.getvalue()


def organize_report_csv(actions: list[OrganizeAction]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "source_path",
            "dest_path",
            "desired_dest_path",
            "category",
            "action",
            "name_conflict",
            "error",
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
                action.error or "",
            ]
        )
    return buf.getvalue()


def pairs_report_csv(pairs: list[PairRecord]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["key", "jpg_path", "raw_path"])
    for pair in pairs:
        writer.writerow([pair.key, pair.jpg_path, pair.raw_path])
    return buf.getvalue()


def orphans_report_csv(orphans_jpg: list[str], orphans_raw: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["type", "path"])
    for path in orphans_jpg:
        writer.writerow(["jpg", path])
    for path in orphans_raw:
        writer.writerow(["raw", path])
    return buf.getvalue()


def _write_text(path: str, content: str) -> None:
    report_dir = os.path.dirname(path)
    if report_dir:
        os.makedirs(report_dir, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(content)


def write_duplicates_report(
    matches: list[DuplicateMatch],
    report_path: str,
    actions: list[DuplicateAction] | None = None,
) -> None:
    _write_text(report_path, duplicates_report_csv(matches, actions))


def write_organize_report(actions: list[OrganizeAction], report_path: str) -> None:
    _write_text(report_path, organize_report_csv(actions))


def write_pairs_report(
    pairs: list[PairRecord],
    orphans_jpg: list[str],
    orphans_raw: list[str],
    pairs_path: str,
    orphans_path: str,
) -> None:
    _write_text(pairs_path, pairs_report_csv(pairs))
    _write_text(orphans_path, orphans_report_csv(orphans_jpg, orphans_raw))
