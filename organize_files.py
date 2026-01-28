"""
Work File Organizer - 工作檔案整理助手（CLI）

功能：
- 依副檔名分類
- 可選時間分層
- 重複檔案偵測（三層比對）並移到 Duplicates/
- 可選檔名清理
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from datetime import datetime

from core import group_duplicates, scan_folder, write_duplicates_report
from core.hashers import full_hash, partial_hash
from core.naming import clean_filename, resolve_destination
from core.types import DuplicateAction, DuplicateMatch, FileInfo
from rules_presets import WORK_PRESET


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
        for info in group:
            if os.path.abspath(info.path).startswith(os.path.abspath(prefer_path) + os.sep):
                return info
    return group[0]


def _category_for_extension(ext: str) -> str:
    ext_lower = ext.lower()
    for category, exts in WORK_PRESET.items():
        if ext_lower in exts:
            return category
    return "Others"


def main() -> None:
    parser = argparse.ArgumentParser(description="工作檔案整理助手（CLI）")
    parser.add_argument("source", help="來源資料夾")
    parser.add_argument(
        "-o",
        "--output",
        default="organized_output",
        help="輸出資料夾（預設: organized_output）",
    )
    parser.add_argument("-r", "--recursive", action="store_true", help="遞迴掃描子資料夾")
    parser.add_argument(
        "--time-partition",
        action="store_true",
        help="時間分層（/YYYY-MM/分類）",
    )
    parser.add_argument("--dry-run", action="store_true", help="預覽模式，不實際移動檔案")
    parser.add_argument(
        "--skip-duplicates",
        action="store_true",
        help="略過重複檔案偵測",
    )
    parser.add_argument(
        "--dupe-strategy",
        default="latest",
        choices=["latest", "earliest", "prefer-path"],
        help="重複檔案保留策略（預設: latest）",
    )
    parser.add_argument(
        "--prefer-path",
        default=None,
        help="保留策略為 prefer-path 時指定路徑前綴",
    )
    parser.add_argument(
        "--partial-size-mb",
        type=int,
        default=1,
        help="partial hash 讀取前/後的大小（MB，預設: 1）",
    )
    parser.add_argument(
        "--full-hash",
        default="sha256",
        choices=["sha256", "xxhash64"],
        help="完整 hash 演算法（預設: sha256）",
    )
    parser.add_argument(
        "--clean-names",
        action="store_true",
        help="啟用檔名清理（移除(1)/(2)、空白正規化、移除特殊字元、衝突補 _001）",
    )
    parser.add_argument(
        "--clean-copy-suffix",
        action="store_true",
        help="移除檔名結尾的 (1)/(2) 等副本後綴",
    )
    parser.add_argument(
        "--clean-normalize-space",
        action="store_true",
        help="空白正規化（多空白合併為一個）",
    )
    parser.add_argument(
        "--clean-remove-special",
        action="store_true",
        help="移除檔名中的特殊字元",
    )
    parser.add_argument(
        "--clean-conflict-width",
        type=int,
        default=None,
        help="命名衝突自動補碼位數（預設: clean-names=3，其餘=1）",
    )

    args = parser.parse_args()

    if args.dupe_strategy == "prefer-path" and not args.prefer_path:
        print("錯誤: dupe-strategy=prefer-path 時必須提供 --prefer-path")
        return
    if not os.path.isdir(args.source):
        print(f"錯誤: 來源資料夾不存在 - {args.source}")
        return

    clean_enabled = (
        args.clean_names
        or args.clean_copy_suffix
        or args.clean_normalize_space
        or args.clean_remove_special
    )
    clean_copy_suffix = args.clean_copy_suffix or args.clean_names
    clean_normalize_space = args.clean_normalize_space or args.clean_names
    clean_remove_special = args.clean_remove_special or args.clean_names
    if args.clean_conflict_width is None:
        conflict_width = 3 if clean_enabled else 1
    else:
        conflict_width = max(args.clean_conflict_width, 0)

    files = scan_folder(args.source, args.recursive)
    print(f"來源資料夾: {len(files)} 個檔案")

    output_root = args.output
    duplicates_dir = os.path.join(output_root, "Duplicates")
    os.makedirs(output_root, exist_ok=True)
    os.makedirs(duplicates_dir, exist_ok=True)

    duplicate_matches: list[DuplicateMatch] = []
    duplicate_actions: list[DuplicateAction] = []
    moved_to_duplicates: set[str] = set()

    if not args.skip_duplicates:
        groups = group_duplicates(
            files,
            partial_bytes=max(args.partial_size_mb, 1) * 1024 * 1024,
            full_hash_algo=args.full_hash,
        )
        for group in groups:
            keep = _pick_keep_for_group(group, args.dupe_strategy, args.prefer_path)
            for info in group:
                if info.path == keep.path:
                    continue
                ph = partial_hash(info.path, max(args.partial_size_mb, 1) * 1024 * 1024)
                fh = full_hash(info.path, algo=args.full_hash)
                if ph is None or fh is None:
                    continue

                filename = os.path.basename(info.path)
                if clean_enabled:
                    filename = clean_filename(
                        filename,
                        remove_copy_suffix=clean_copy_suffix,
                        normalize_space=clean_normalize_space,
                        remove_special=clean_remove_special,
                    )

                desired_dest, dest, name_conflict = resolve_destination(
                    duplicates_dir,
                    filename,
                    conflict_width,
                )

                action = "preview" if args.dry_run else "moved"
                if not args.dry_run:
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
                        strategy=args.dupe_strategy,
                        partial_hash=ph,
                        full_hash=fh,
                    )
                )

    # Organize remaining files
    organize_ops: list[tuple[str, str, str, str, str, bool]] = []
    for info in files:
        if info.path in moved_to_duplicates:
            continue
        category = _category_for_extension(info.ext)
        if args.time_partition:
            month = datetime.fromtimestamp(info.mtime).strftime("%Y-%m")
            target_dir = os.path.join(output_root, month, category)
        else:
            target_dir = os.path.join(output_root, category)
        os.makedirs(target_dir, exist_ok=True)

        filename = os.path.basename(info.path)
        if clean_enabled:
            filename = clean_filename(
                filename,
                remove_copy_suffix=clean_copy_suffix,
                normalize_space=clean_normalize_space,
                remove_special=clean_remove_special,
            )

        desired_dest, dest, name_conflict = resolve_destination(
            target_dir,
            filename,
            conflict_width,
        )
        action = "preview" if args.dry_run else "moved"
        if not args.dry_run:
            shutil.move(info.path, dest)
        organize_ops.append((info.path, dest, desired_dest, category, action, name_conflict))

    # Reports
    if duplicate_matches:
        dupe_report = os.path.join(duplicates_dir, "duplicates_report.csv")
        write_duplicates_report(duplicate_matches, dupe_report, actions=duplicate_actions)
        print(f"重複檔案報表已輸出: {dupe_report}")

    organize_report = os.path.join(output_root, "organize_report.csv")
    with open(organize_report, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "source_path",
                "dest_path",
                "desired_dest_path",
                "category",
                "action",
                "name_conflict",
            ]
        )
        for src, dest, desired, category, action, name_conflict in organize_ops:
            writer.writerow(
                [
                    src,
                    dest,
                    desired,
                    category,
                    action,
                    "1" if name_conflict else "0",
                ]
            )
    print(f"整理報表已輸出: {organize_report}")

    print(
        f"\n摘要: 來源 {len(files)} 個，"
        f"重複移動 {len(moved_to_duplicates)} 個，"
        f"整理移動 {len(organize_ops)} 個"
    )


if __name__ == "__main__":
    main()
