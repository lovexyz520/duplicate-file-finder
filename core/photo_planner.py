from __future__ import annotations

import os
from datetime import datetime
from typing import Mapping

from .dupe import group_duplicates
from .hashers import full_hash, partial_hash
from .media_scanner import scan_media_folder
from .media_types import MediaFileInfo, PhotoAction, PhotoPlan
from .naming import resolve_destination
from .photo_pairing import pair_media_files, pick_pair_folder
from .types import DuplicateAction, DuplicateMatch, FileInfo


def _date_bucket(shot_time: datetime | None, fallback_mtime: float) -> str:
    if shot_time is None:
        return datetime.fromtimestamp(fallback_mtime).strftime("%Y-%m-%d")
    return shot_time.strftime("%Y-%m-%d")


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


def _media_to_fileinfo(info: MediaFileInfo) -> FileInfo:
    return FileInfo(
        path=info.path,
        size=info.size,
        mtime=info.mtime,
        ctime=info.ctime,
        ext=info.ext,
    )


def _build_photo_action(
    info: MediaFileInfo,
    dest_folder: str,
    pair_key: str | None,
    pair_role: str | None,
    conflict_suffix_width: int,
) -> PhotoAction:
    filename = os.path.basename(info.path)
    desired_dest, dest, name_conflict = resolve_destination(
        dest_folder,
        filename,
        conflict_suffix_width,
    )
    return PhotoAction(
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
) -> PhotoPlan:
    media_files = scan_media_folder(source_folder, recursive, preset)

    file_infos = [_media_to_fileinfo(m) for m in media_files]
    moved_to_duplicates: set[str] = set()
    duplicate_matches: list[DuplicateMatch] = []
    duplicate_actions: list[DuplicateAction] = []

    if enable_duplicates and file_infos:
        partial_bytes = max(partial_size_mb, 1) * 1024 * 1024
        groups = group_duplicates(file_infos, partial_bytes, full_hash_algo)
        duplicates_dir = os.path.join(output_folder, "Duplicates")
        os.makedirs(duplicates_dir, exist_ok=True)

        for group in groups:
            keep = _pick_keep_for_group(group, dupe_strategy, prefer_path)
            for info in group:
                if info.path == keep.path:
                    continue
                ph = partial_hash(info.path, partial_bytes)
                fh = full_hash(info.path, algo=full_hash_algo)
                if ph is None or fh is None:
                    continue
                desired_dest, dest, name_conflict = resolve_destination(
                    duplicates_dir,
                    os.path.basename(info.path),
                    conflict_suffix_width,
                )
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
                        action="preview",
                        strategy=dupe_strategy,
                        partial_hash=ph,
                        full_hash=fh,
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

        if layout == "by-date-type":
            date_bucket = _date_bucket(info.shot_time, info.mtime)
            target_dir = os.path.join(output_folder, date_bucket, info.category)
        elif layout == "per-pair-folder":
            if pair_key:
                target_dir = pick_pair_folder(pair_key, output_folder)
            else:
                date_bucket = _date_bucket(info.shot_time, info.mtime)
                target_dir = os.path.join(output_folder, "Unpaired", date_bucket, info.category)
        else:
            date_bucket = _date_bucket(info.shot_time, info.mtime)
            target_dir = os.path.join(output_folder, date_bucket, info.category)

        os.makedirs(target_dir, exist_ok=True)
        actions.append(
            _build_photo_action(
                info,
                target_dir,
                pair_key=pair_key,
                pair_role=pair_role,
                conflict_suffix_width=conflict_suffix_width,
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
