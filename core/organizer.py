from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Mapping

from .dupe import group_duplicates
from .hashers import full_hash, partial_hash
from .naming import clean_filename, resolve_destination
from .report import write_duplicates_report, write_organize_report
from .scanner import scan_folder
from .types import DuplicateAction, DuplicateMatch, FileInfo, OrganizeAction

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


def _pick_keep_for_group(
    group: list[FileInfo],
    strategy: str,
    prefer_path: str | None,
) -> FileInfo:
    if strategy == "latest":
        return max(group, key=lambda f: f.mtime)
    if strategy == "earliest":
        return min(group, key=lambda f: f.ctime)
    if strategy == "prefer-path" and prefer_path:
        prefix = os.path.abspath(prefer_path)
        with_sep = prefix + os.sep
        for info in group:
            path = os.path.abspath(info.path)
            if path == prefix or path.startswith(with_sep):
                return info
    return group[0]


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
) -> tuple[
    int,
    list[DuplicateMatch],
    list[DuplicateAction],
    list[OrganizeAction],
]:
    files = scan_folder(source_folder, recursive)
    os.makedirs(output_folder, exist_ok=True)
    duplicates_dir = os.path.join(output_folder, "Duplicates")
    os.makedirs(duplicates_dir, exist_ok=True)

    preset_map = preset or DEFAULT_PRESET
    partial_bytes = max(partial_size_mb, 1) * 1024 * 1024

    duplicate_matches: list[DuplicateMatch] = []
    duplicate_actions: list[DuplicateAction] = []
    moved_to_duplicates: set[str] = set()

    if not skip_duplicates:
        groups = group_duplicates(
            files,
            partial_bytes=partial_bytes,
            full_hash_algo=full_hash_algo,
        )
        for group in groups:
            keep = _pick_keep_for_group(group, dupe_strategy, prefer_path)
            for info in group:
                if info.path == keep.path:
                    continue
                ph = partial_hash(info.path, partial_bytes)
                fh = full_hash(info.path, algo=full_hash_algo)
                if ph is None or fh is None:
                    continue

                filename = os.path.basename(info.path)
                if clean_names:
                    filename = clean_filename(
                        filename,
                        remove_copy_suffix=clean_copy_suffix,
                        normalize_space=clean_normalize_space,
                        remove_special=clean_remove_special,
                    )

                desired_dest, dest, name_conflict = resolve_destination(
                    duplicates_dir,
                    filename,
                    conflict_suffix_width,
                )

                action = "preview" if dry_run else "moved"
                if not dry_run:
                    shutil.move(info.path, dest)

                moved_to_duplicates.add(info.path)

                duplicate_matches.append(
                    DuplicateMatch(
                        original=keep,
                        duplicate=info,
                        partial_hash=ph,
                        full_hash=fh,
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
                        partial_hash=ph,
                        full_hash=fh,
                    )
                )

    organize_actions: list[OrganizeAction] = []
    for info in files:
        if info.path in moved_to_duplicates:
            continue
        category = _category_for_extension(info.ext, preset_map)
        if time_partition:
            month = datetime.fromtimestamp(info.mtime).strftime("%Y-%m")
            target_dir = os.path.join(output_folder, month, category)
        else:
            target_dir = os.path.join(output_folder, category)
        os.makedirs(target_dir, exist_ok=True)

        filename = os.path.basename(info.path)
        if clean_names:
            filename = clean_filename(
                filename,
                remove_copy_suffix=clean_copy_suffix,
                normalize_space=clean_normalize_space,
                remove_special=clean_remove_special,
            )

        desired_dest, dest, name_conflict = resolve_destination(
            target_dir,
            filename,
            conflict_suffix_width,
        )

        action = "preview" if dry_run else "moved"
        if not dry_run:
            shutil.move(info.path, dest)

        organize_actions.append(
            OrganizeAction(
                source_path=info.path,
                dest_path=dest,
                desired_dest_path=desired_dest,
                category=category,
                action=action,
                name_conflict=name_conflict,
            )
        )

    if duplicate_matches:
        dupe_report = os.path.join(duplicates_dir, "duplicates_report.csv")
        write_duplicates_report(duplicate_matches, dupe_report, actions=duplicate_actions)

    organize_report = os.path.join(output_folder, "organize_report.csv")
    write_organize_report(organize_actions, organize_report)

    return len(files), duplicate_matches, duplicate_actions, organize_actions
