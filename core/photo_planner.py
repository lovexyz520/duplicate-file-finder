from __future__ import annotations

import os
from datetime import datetime
from typing import Callable, Mapping

from .dupe import group_duplicates, pick_keep_for_group
from .media_scanner import scan_media_folder
from .media_types import MediaFileInfo, PhotoAction, PhotoPlan
from .naming import DestinationResolver
from .photo_pairing import pair_media_files, pick_pair_folder
from .types import DuplicateAction, DuplicateMatch, FileInfo

# progress(stage, done, total)，stage: "scan" | "hash"
StageProgress = Callable[[str, int, int], None]


def _date_bucket(shot_time: datetime | None, fallback_mtime: float) -> str:
    if shot_time is None:
        return datetime.fromtimestamp(fallback_mtime).strftime("%Y-%m-%d")
    return shot_time.strftime("%Y-%m-%d")


def _media_to_fileinfo(info: MediaFileInfo) -> FileInfo:
    return FileInfo(
        path=info.path,
        size=info.size,
        mtime=info.mtime,
        ctime=info.ctime,
        ext=info.ext,
    )


def plan_photo_actions(
    source_folder: str,
    output_folder: str,
    recursive: bool,
    preset: Mapping[str, set[str]],
    layout: str,
    pair_key_mode: str,
    enable_duplicates: bool,
    dupe_strategy: str,
    prefer_path: str | None,
    partial_size_mb: int,
    full_hash_algo: str,
    conflict_suffix_width: int = 3,
    min_size: int = 0,
    include_hidden: bool = True,
    exclude_dirs: set[str] | None = None,
    progress: StageProgress | None = None,
) -> PhotoPlan:
    """規劃攝影素材整理。純規劃，不觸碰磁碟。"""
    scan_progress = None
    if progress:
        scan_progress = lambda done, total: progress("scan", done, total)  # noqa: E731
    media_files = scan_media_folder(
        source_folder,
        recursive,
        preset,
        min_size=min_size,
        include_hidden=include_hidden,
        exclude_dirs=exclude_dirs,
        progress=scan_progress,
    )

    file_infos = [_media_to_fileinfo(m) for m in media_files]
    moved_to_duplicates: set[str] = set()
    duplicate_matches: list[DuplicateMatch] = []
    duplicate_actions: list[DuplicateAction] = []
    resolver = DestinationResolver()

    if enable_duplicates and file_infos:
        partial_bytes = max(partial_size_mb, 1) * 1024 * 1024
        hash_progress = None
        if progress:
            hash_progress = lambda done, total: progress("hash", done, total)  # noqa: E731
        groups = group_duplicates(
            file_infos, partial_bytes, full_hash_algo, progress=hash_progress
        )
        duplicates_dir = os.path.join(output_folder, "Duplicates")

        for group in groups:
            keep = pick_keep_for_group(
                [g.info for g in group], dupe_strategy, prefer_path
            )
            for grouped in group:
                info = grouped.info
                if info.path == keep.path:
                    continue
                desired_dest, dest, name_conflict = resolver.resolve(
                    duplicates_dir,
                    os.path.basename(info.path),
                    conflict_suffix_width,
                )
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
                        action="preview",
                        strategy=dupe_strategy,
                        partial_hash=grouped.partial_hash,
                        full_hash=grouped.full_hash,
                    )
                )
                moved_to_duplicates.add(info.path)

    remaining_media = [m for m in media_files if m.path not in moved_to_duplicates]
    pairs, orphan_jpgs, orphan_raws = pair_media_files(remaining_media, pair_key_mode)

    pair_map: dict[str, str] = {}
    for pair in pairs:
        pair_map[pair.jpg_path] = pair.key
        pair_map[pair.raw_path] = pair.key

    actions: list[PhotoAction] = []
    for info in remaining_media:
        pair_key = pair_map.get(info.path)
        pair_role = None
        if info.category in {"RAW", "JPG"}:
            pair_role = info.category.lower()

        if layout == "per-pair-folder" and pair_key:
            target_dir = pick_pair_folder(pair_key, output_folder)
        elif layout == "per-pair-folder":
            date_bucket = _date_bucket(info.shot_time, info.mtime)
            target_dir = os.path.join(output_folder, "Unpaired", date_bucket, info.category)
        else:
            date_bucket = _date_bucket(info.shot_time, info.mtime)
            target_dir = os.path.join(output_folder, date_bucket, info.category)

        filename = os.path.basename(info.path)
        desired_dest, dest, name_conflict = resolver.resolve(
            target_dir,
            filename,
            conflict_suffix_width,
        )
        actions.append(
            PhotoAction(
                source_path=info.path,
                dest_path=dest,
                desired_dest_path=desired_dest,
                category=info.category,
                action="preview",
                name_conflict=name_conflict,
                pair_key=pair_key,
                pair_role=pair_role,
                shot_date=_date_bucket(info.shot_time, info.mtime),
            )
        )

    return PhotoPlan(
        media_files=media_files,
        pairs=[(p.key, p.jpg_path, p.raw_path) for p in pairs],
        orphan_jpgs=orphan_jpgs,
        orphan_raws=orphan_raws,
        duplicate_matches=duplicate_matches,
        duplicate_actions=duplicate_actions,
        photo_actions=actions,
    )
