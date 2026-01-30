from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from typing import Iterable

from .naming import resolve_destination


JPG_EXTS_DEFAULT = {".jpg", ".jpeg", ".heic"}
RAW_EXTS_DEFAULT = {".arw", ".cr2", ".nef", ".raf", ".dng", ".rw2"}


@dataclass(frozen=True)
class PairRecord:
    key: str
    jpg_path: str
    raw_path: str


@dataclass(frozen=True)
class PairAction:
    key: str
    role: str  # "jpg" | "raw"
    src_path: str
    dest_path: str
    action: str  # "preview" | "copied" | "moved"
    name_conflict: bool


def _iter_files(folder: str, recursive: bool) -> Iterable[str]:
    if recursive:
        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                yield os.path.join(root, filename)
    else:
        for filename in os.listdir(folder):
            path = os.path.join(folder, filename)
            if os.path.isfile(path):
                yield path


def _collect_paths(folder: str, recursive: bool, exts: set[str]) -> list[str]:
    paths: list[str] = []
    exts_lower = {ext.lower() for ext in exts}
    for path in _iter_files(folder, recursive):
        _, ext = os.path.splitext(path)
        if ext.lower() in exts_lower:
            paths.append(path)
    return paths


def _pair_key(path: str, key_mode: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    if key_mode == "stem":
        return stem.lower()
    if key_mode == "stem+parent":
        parent = os.path.basename(os.path.dirname(path))
        return f"{parent}-{stem}".lower()
    return stem.lower()


def _index_by_key(paths: list[str], key_mode: str) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for path in paths:
        key = _pair_key(path, key_mode)
        index.setdefault(key, []).append(path)
    for key in index:
        index[key].sort()
    return index


def pair_by_stem(
    jpg_folder: str,
    raw_folder: str,
    recursive: bool = False,
    jpg_exts: set[str] | None = None,
    raw_exts: set[str] | None = None,
    key_mode: str = "stem",
) -> tuple[list[PairRecord], list[str], list[str]]:
    jpg_exts = jpg_exts or JPG_EXTS_DEFAULT
    raw_exts = raw_exts or RAW_EXTS_DEFAULT

    jpg_paths = _collect_paths(jpg_folder, recursive, jpg_exts)
    raw_paths = _collect_paths(raw_folder, recursive, raw_exts)

    jpg_index = _index_by_key(jpg_paths, key_mode)
    raw_index = _index_by_key(raw_paths, key_mode)

    pairs: list[PairRecord] = []
    orphan_jpgs: list[str] = []
    orphan_raws: list[str] = []

    all_keys = set(jpg_index) | set(raw_index)
    for key in sorted(all_keys):
        jpg_list = jpg_index.get(key, [])
        raw_list = raw_index.get(key, [])
        pair_count = min(len(jpg_list), len(raw_list))
        for idx in range(pair_count):
            pairs.append(PairRecord(key=key, jpg_path=jpg_list[idx], raw_path=raw_list[idx]))
        if len(jpg_list) > pair_count:
            orphan_jpgs.extend(jpg_list[pair_count:])
        if len(raw_list) > pair_count:
            orphan_raws.extend(raw_list[pair_count:])

    return pairs, orphan_jpgs, orphan_raws


def _safe_key_folder(key: str) -> str:
    return re.sub(r"[^\w-]", "_", key).strip("_") or "pair"


def plan_pair_layout(
    pairs: list[PairRecord],
    output_folder: str,
    layout: str,
    action: str,
    conflict_suffix_width: int = 3,
) -> list[PairAction]:
    os.makedirs(output_folder, exist_ok=True)
    planned: list[PairAction] = []

    for pair in pairs:
        if layout == "raw-with-jpg":
            target_dir = os.path.join(output_folder, "RAW")
        elif layout == "per-pair-folder":
            target_dir = os.path.join(output_folder, "Pairs", _safe_key_folder(pair.key))
        elif layout == "split-index":
            target_dir = os.path.join(output_folder, "RAW")
        else:
            target_dir = output_folder

        os.makedirs(target_dir, exist_ok=True)

        raw_name = os.path.basename(pair.raw_path)
        desired_raw, raw_dest, raw_conflict = resolve_destination(
            target_dir,
            raw_name,
            conflict_suffix_width,
        )
        planned.append(
            PairAction(
                key=pair.key,
                role="raw",
                src_path=pair.raw_path,
                dest_path=raw_dest,
                action=action,
                name_conflict=raw_conflict,
            )
        )

        if layout == "split-index":
            jpg_dir = os.path.join(output_folder, "Photos")
            os.makedirs(jpg_dir, exist_ok=True)
            jpg_name = os.path.basename(pair.jpg_path)
            desired_jpg, jpg_dest, jpg_conflict = resolve_destination(
                jpg_dir,
                jpg_name,
                conflict_suffix_width,
            )
        else:
            jpg_name = os.path.basename(pair.jpg_path)
            desired_jpg, jpg_dest, jpg_conflict = resolve_destination(
                target_dir,
                jpg_name,
                conflict_suffix_width,
            )

        planned.append(
            PairAction(
                key=pair.key,
                role="jpg",
                src_path=pair.jpg_path,
                dest_path=jpg_dest,
                action=action,
                name_conflict=jpg_conflict,
            )
        )

    return planned


def execute_pair_actions(
    actions: list[PairAction],
    dry_run: bool = False,
    move: bool = False,
) -> tuple[int, list[PairAction]]:
    copied = 0
    completed: list[PairAction] = []
    for action in actions:
        if dry_run:
            completed.append(
                PairAction(
                    key=action.key,
                    role=action.role,
                    src_path=action.src_path,
                    dest_path=action.dest_path,
                    action="preview",
                    name_conflict=action.name_conflict,
                )
            )
            continue

        if move:
            shutil.move(action.src_path, action.dest_path)
            verb = "moved"
        else:
            shutil.copy2(action.src_path, action.dest_path)
            verb = "copied"
        copied += 1
        completed.append(
            PairAction(
                key=action.key,
                role=action.role,
                src_path=action.src_path,
                dest_path=action.dest_path,
                action=verb,
                name_conflict=action.name_conflict,
            )
        )

    return copied, completed

