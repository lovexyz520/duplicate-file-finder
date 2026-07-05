from __future__ import annotations

import os
import re


def clean_filename(
    filename: str,
    remove_copy_suffix: bool,
    normalize_space: bool,
    remove_special: bool,
) -> str:
    stem, ext = os.path.splitext(filename)
    cleaned = stem
    if remove_copy_suffix:
        cleaned = re.sub(r"\s*\(\d+\)$", "", cleaned)
    if normalize_space:
        cleaned = cleaned.replace("　", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if remove_special:
        cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    if not cleaned:
        cleaned = "file"
    return f"{cleaned}{ext}"


def safe_key_folder(key: str) -> str:
    return re.sub(r"[^\w-]", "_", key).strip("_") or "pair"


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


class DestinationResolver:
    """解析目的地路徑並記住同一批計畫中已配置的路徑。

    只檢查磁碟上的既有檔案不夠：先規劃、後執行的流程中，兩個同名來源檔
    在規劃當下都不存在於目的地，會解析出同一個路徑，執行時互相覆蓋。
    """

    def __init__(self) -> None:
        self._reserved: set[str] = set()

    def resolve(
        self,
        output_folder: str,
        filename: str,
        conflict_suffix_width: int,
    ) -> tuple[str, str, bool]:
        desired_dest = os.path.join(output_folder, filename)
        dest = desired_dest
        name_conflict = False
        if os.path.exists(dest) or _norm(dest) in self._reserved:
            name_conflict = True
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(dest) or _norm(dest) in self._reserved:
                if conflict_suffix_width <= 0:
                    suffix = str(counter)
                else:
                    suffix = str(counter).zfill(conflict_suffix_width)
                dest = os.path.join(output_folder, f"{base}_{suffix}{ext}")
                counter += 1
        self._reserved.add(_norm(dest))
        return desired_dest, dest, name_conflict


def resolve_destination(
    output_folder: str,
    filename: str,
    conflict_suffix_width: int,
    resolver: DestinationResolver | None = None,
) -> tuple[str, str, bool]:
    if resolver is None:
        resolver = DestinationResolver()
    return resolver.resolve(output_folder, filename, conflict_suffix_width)
