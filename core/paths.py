from __future__ import annotations

import os


def path_is_within(path: str, prefix: str) -> bool:
    normalized = os.path.normcase(os.path.abspath(path))
    prefix_normalized = os.path.normcase(os.path.abspath(prefix))
    if normalized == prefix_normalized:
        return True
    return normalized.startswith(prefix_normalized + os.sep)


def check_overlapping(folder1: str, folder2: str) -> str | None:
    """檢查兩個資料夾是否重疊。

    Returns:
        'same' | 'folder1_contains_folder2' | 'folder2_contains_folder1' | None
    """
    path1 = os.path.normcase(os.path.abspath(folder1))
    path2 = os.path.normcase(os.path.abspath(folder2))
    if path1 == path2:
        return "same"
    if path2.startswith(path1 + os.sep):
        return "folder1_contains_folder2"
    if path1.startswith(path2 + os.sep):
        return "folder2_contains_folder1"
    return None
