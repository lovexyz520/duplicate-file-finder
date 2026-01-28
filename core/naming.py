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
        cleaned = cleaned.replace("\u3000", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if remove_special:
        cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    if not cleaned:
        cleaned = "file"
    return f"{cleaned}{ext}"


def resolve_destination(
    output_folder: str,
    filename: str,
    conflict_suffix_width: int,
) -> tuple[str, str, bool]:
    desired_dest = os.path.join(output_folder, filename)
    dest = desired_dest
    name_conflict = False
    if os.path.exists(dest):
        name_conflict = True
        base, ext = os.path.splitext(os.path.basename(dest))
        counter = 1
        while os.path.exists(dest):
            if conflict_suffix_width <= 0:
                suffix = str(counter)
            else:
                suffix = str(counter).zfill(conflict_suffix_width)
            dest = os.path.join(output_folder, f"{base}_{suffix}{ext}")
            counter += 1
    return desired_dest, dest, name_conflict
