from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Callable, Mapping

from .dupe import group_duplicates, pick_keep_for_group
from .naming import DestinationResolver, clean_filename
from .report import write_duplicates_report, write_organize_report
from .scanner import scan_folder
from .types import DuplicateAction, DuplicateMatch, OrganizeAction

# progress(stage, done, total)，stage: "hash" | "move"
StageProgress = Callable[[str, int, int], None]

DEFAULT_PRESET: Mapping[str, set[str]] = {
    "Docs": {".doc", ".docx", ".txt", ".md"},
    "PDF": {".pdf"},
    "Sheets": {".xls", ".xlsx", ".csv"},
    "Slides": {".ppt", ".pptx"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".json", ".ts", ".html", ".css", ".yml", ".yaml"},
    "Others": set(),
}


def _category_for_extension(ext: str, preset: Mapping[str, set[str]]) -> str:
    ext_lower = ext.lower()
    for category, exts in preset.items():
        if ext_lower in exts:
            return category
    return "Others"


def organize(
    source_folder: str,
    output_folder: str,
    recursive: bool = False,
    time_partition: bool = False,
    dry_run: bool = False,
    skip_duplicates: bool = False,
    dupe_strategy: str = "latest",
    prefer_path: str | None = None,
    partial_size_mb: int = 1,
    full_hash_algo: str = "sha256",
    clean_names: bool = False,
    clean_copy_suffix: bool = False,
    clean_normalize_space: bool = False,
    clean_remove_special: bool = False,
    conflict_suffix_width: int = 3,
    preset: Mapping[str, set[str]] | None = None,
    min_size: int = 0,
    include_hidden: bool = True,
    exclude_dirs: set[str] | None = None,
    write_reports: bool = True,
    progress: StageProgress | None = None,
) -> tuple[
    int,
    list[DuplicateMatch],
    list[DuplicateAction],
    list[OrganizeAction],
]:
    """整理來源資料夾。dry_run 時不觸碰磁碟（不建資料夾、不移動、不寫報表）。"""
    files = scan_folder(
        source_folder,
        recursive,
        min_size=min_size,
        include_hidden=include_hidden,
        exclude_dirs=exclude_dirs,
    )
    duplicates_dir = os.path.join(output_folder, "Duplicates")

    preset_map = preset or DEFAULT_PRESET
    partial_bytes = max(partial_size_mb, 1) * 1024 * 1024

    duplicate_matches: list[DuplicateMatch] = []
    duplicate_actions: list[DuplicateAction] = []
    moved_to_duplicates: set[str] = set()
    resolver = DestinationResolver()

    def _clean(filename: str) -> str:
        if not clean_names:
            return filename
        return clean_filename(
            filename,
            remove_copy_suffix=clean_copy_suffix,
            normalize_space=clean_normalize_space,
            remove_special=clean_remove_special,
        )

    if not skip_duplicates:
        hash_progress = None
        if progress:
            hash_progress = lambda done, total: progress("hash", done, total)  # noqa: E731
        groups = group_duplicates(
            files,
            partial_bytes=partial_bytes,
            full_hash_algo=full_hash_algo,
            progress=hash_progress,
        )
        for group in groups:
            keep = pick_keep_for_group(
                [g.info for g in group], dupe_strategy, prefer_path
            )
            for grouped in group:
                info = grouped.info
                if info.path == keep.path:
                    continue

                filename = _clean(os.path.basename(info.path))
                desired_dest, dest, name_conflict = resolver.resolve(
                    duplicates_dir,
                    filename,
                    conflict_suffix_width,
                )

                action = "preview"
                error = None
                if not dry_run:
                    try:
                        os.makedirs(duplicates_dir, exist_ok=True)
                        shutil.move(info.path, dest)
                        action = "moved"
                    except Exception as exc:  # noqa: BLE001 - 逐檔隔離錯誤
                        action = "failed"
                        error = str(exc)

                if action != "failed":
                    moved_to_duplicates.add(info.path)

                duplicate_matches.append(
                    DuplicateMatch(
                        original=keep,
                        duplicate=info,
                        partial_hash=grouped.partial_hash,
                        full_hash=grouped.full_hash,
                    )
                )
                duplicate_actions.append(
                    DuplicateAction(
                        original=keep,
                        duplicate=info,
                        keep_path=keep.path,
                        move_path=dest,
                        desired_move_path=desired_dest,
                        name_conflict=name_conflict,
                        action=action,
                        strategy=dupe_strategy,
                        partial_hash=grouped.partial_hash,
                        full_hash=grouped.full_hash,
                        error=error,
                    )
                )

    organize_actions: list[OrganizeAction] = []
    remaining = [f for f in files if f.path not in moved_to_duplicates]
    total_remaining = len(remaining)
    for index, info in enumerate(remaining, start=1):
        if progress:
            progress("move", index, total_remaining)
        category = _category_for_extension(info.ext, preset_map)
        if time_partition:
            month = datetime.fromtimestamp(info.mtime).strftime("%Y-%m")
            target_dir = os.path.join(output_folder, month, category)
        else:
            target_dir = os.path.join(output_folder, category)

        filename = _clean(os.path.basename(info.path))
        desired_dest, dest, name_conflict = resolver.resolve(
            target_dir,
            filename,
            conflict_suffix_width,
        )

        action = "preview"
        error = None
        if not dry_run:
            try:
                os.makedirs(target_dir, exist_ok=True)
                shutil.move(info.path, dest)
                action = "moved"
            except Exception as exc:  # noqa: BLE001 - 逐檔隔離錯誤
                action = "failed"
                error = str(exc)

        organize_actions.append(
            OrganizeAction(
                source_path=info.path,
                dest_path=dest,
                desired_dest_path=desired_dest,
                category=category,
                action=action,
                name_conflict=name_conflict,
                error=error,
            )
        )

    if write_reports and not dry_run:
        if duplicate_matches:
            dupe_report = os.path.join(duplicates_dir, "duplicates_report.csv")
            write_duplicates_report(
                duplicate_matches, dupe_report, actions=duplicate_actions
            )
        organize_report = os.path.join(output_folder, "organize_report.csv")
        write_organize_report(organize_actions, organize_report)

    return len(files), duplicate_matches, duplicate_actions, organize_actions


def organize_actions_to_records(actions: list[OrganizeAction]) -> list[dict]:
    from .oplog import make_record

    records = []
    for action in actions:
        if action.action == "preview":
            continue
        records.append(
            make_record(
                op="move",
                source=action.source_path,
                dest=action.dest_path,
                status=action.action,
                kind="organize",
                error=action.error,
                category=action.category,
                name_conflict=action.name_conflict,
            )
        )
    return records
