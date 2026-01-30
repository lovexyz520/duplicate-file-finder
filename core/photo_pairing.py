from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Iterable

from .media_types import MediaFileInfo
from .pairing import PairRecord


def _safe_key_folder(key: str) -> str:
    return re.sub(r"[^\w-]", "_", key).strip("_") or "pair"


def _key_by_stem(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem.lower()


def _key_by_stem_parent(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    parent = os.path.basename(os.path.dirname(path))
    return f"{parent}-{stem}".lower()


def _key_by_exif(info: MediaFileInfo) -> str | None:
    if info.shot_time is None:
        return None
    stamp = info.shot_time.strftime("%Y%m%d%H%M%S")
    model = info.camera_model or ""
    return f"{stamp}-{model}".lower()


def _key_for_info(info: MediaFileInfo, mode: str) -> str | None:
    if mode == "stem":
        return _key_by_stem(info.path)
    if mode == "stem+parent":
        return _key_by_stem_parent(info.path)
    if mode == "exif":
        return _key_by_exif(info)
    return _key_by_stem(info.path)


def _index_by_key(infos: Iterable[MediaFileInfo], mode: str) -> dict[str, list[MediaFileInfo]]:
    index: dict[str, list[MediaFileInfo]] = {}
    for info in infos:
        key = _key_for_info(info, mode)
        if not key:
            continue
        index.setdefault(key, []).append(info)
    for key in index:
        index[key].sort(key=lambda item: item.path)
    return index


def pair_media_files(
    media_files: list[MediaFileInfo],
    key_mode: str,
) -> tuple[list[PairRecord], list[str], list[str]]:
    jpgs = [m for m in media_files if m.category == "JPG"]
    raws = [m for m in media_files if m.category == "RAW"]

    jpg_index = _index_by_key(jpgs, key_mode)
    raw_index = _index_by_key(raws, key_mode)

    pairs: list[PairRecord] = []
    orphan_jpgs: list[str] = []
    orphan_raws: list[str] = []

    all_keys = set(jpg_index) | set(raw_index)
    for key in sorted(all_keys):
        jpg_list = jpg_index.get(key, [])
        raw_list = raw_index.get(key, [])
        pair_count = min(len(jpg_list), len(raw_list))
        for idx in range(pair_count):
            pairs.append(
                PairRecord(
                    key=key,
                    jpg_path=jpg_list[idx].path,
                    raw_path=raw_list[idx].path,
                )
            )
        if len(jpg_list) > pair_count:
            orphan_jpgs.extend([p.path for p in jpg_list[pair_count:]])
        if len(raw_list) > pair_count:
            orphan_raws.extend([p.path for p in raw_list[pair_count:]])

    return pairs, orphan_jpgs, orphan_raws


def pick_pair_folder(key: str, output_folder: str) -> str:
    return os.path.join(output_folder, "Pairs", _safe_key_folder(key))
