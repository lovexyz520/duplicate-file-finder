"""
Work File Organizer - 工作檔案整理助手（CLI）

功能：
- 依副檔名分類
- 可選時間分層
- 重複檔案偵測並移到 Duplicates/
- 可選檔名清理
"""

from __future__ import annotations

import argparse
import os

from core import organize
from rules_presets import WORK_PRESET


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

    total_files, duplicate_matches, _, organize_actions = organize(
        source_folder=args.source,
        output_folder=args.output,
        recursive=args.recursive,
        time_partition=args.time_partition,
        dry_run=args.dry_run,
        skip_duplicates=args.skip_duplicates,
        dupe_strategy=args.dupe_strategy,
        prefer_path=args.prefer_path,
        partial_size_mb=args.partial_size_mb,
        full_hash_algo=args.full_hash,
        clean_names=clean_enabled,
        clean_copy_suffix=clean_copy_suffix,
        clean_normalize_space=clean_normalize_space,
        clean_remove_special=clean_remove_special,
        conflict_suffix_width=conflict_width,
        preset=WORK_PRESET,
    )

    print(f"來源資料夾: {total_files} 個檔案")
    if duplicate_matches:
        print(f"重複檔案報表已輸出: {os.path.join(args.output, 'Duplicates', 'duplicates_report.csv')}")
    print(f"整理報表已輸出: {os.path.join(args.output, 'organize_report.csv')}")
    print(
        f"\n摘要: 來源 {total_files} 個，"
        f"重複移動 {len(duplicate_matches)} 個，"
        f"整理移動 {len(organize_actions)} 個"
    )


if __name__ == "__main__":
    main()
