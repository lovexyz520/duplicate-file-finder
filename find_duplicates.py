"""
Duplicate File Finder - 重複檔案搜尋工具

比對兩個資料夾，找出並移動重複的檔案。

運作流程：
1. 掃描兩個資料夾中的檔案
2. 先比對檔案大小，大小不同則跳過（效能優化）
3. 先做 partial hash（前/後 1MB 的 xxhash）
4. partial hash 相同時做完整 SHA256
5. 將 folder2 中的重複檔案移動到輸出資料夾

使用方式：
    uv run find_duplicates.py [folder1] [folder2] [-o OUTPUT] [-r] [--dry-run]
        [--partial-size-mb N] [--full-hash sha256|xxhash64]
        [--keep-strategy folder1|folder2|latest|earliest|prefer-path]
        [--prefer-path PATH] [--move-scope folder2|both]
"""

import argparse
import os

from core import find_duplicates_between, move_duplicates, scan_folder, write_duplicates_report

# 預設資料夾路徑
DEFAULT_FOLDER1 = 'folder1'
DEFAULT_FOLDER2 = 'folder2'
DEFAULT_OUTPUT = 'output_folder'

# 舊路徑參考：
# folder1 = 'E://待整理 poto//mobile phone//手機備份//photo'
# folder2 = 'E://待整理 poto//mobile phone//手機備份//photo'
# output_folder = 'E://待整理 poto//mobile phone//手機備份//output_folder'


def check_overlapping_folders(folder1, folder2):
    """檢查兩個資料夾是否有重疊

    Returns:
        str: 重疊類型 ('same', 'folder1_contains_folder2', 'folder2_contains_folder1', None)
    """
    path1 = os.path.abspath(folder1)
    path2 = os.path.abspath(folder2)

    if path1 == path2:
        return 'same'

    # 確保路徑結尾有分隔符，避免誤判（如 /foo 和 /foobar）
    path1_with_sep = path1 + os.sep
    path2_with_sep = path2 + os.sep

    if path2.startswith(path1_with_sep):
        return 'folder1_contains_folder2'
    if path1.startswith(path2_with_sep):
        return 'folder2_contains_folder1'

    return None


def main():
    parser = argparse.ArgumentParser(description="比對兩個資料夾，找出並移動重複的檔案")
    parser.add_argument("folder1", nargs="?", default=DEFAULT_FOLDER1, help="第一個資料夾路徑")
    parser.add_argument("folder2", nargs="?", default=DEFAULT_FOLDER2, help="第二個資料夾路徑")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="輸出資料夾路徑")
    parser.add_argument("-r", "--recursive", action="store_true", help="遞迴掃描子資料夾")
    parser.add_argument("--dry-run", action="store_true", help="預覽模式，不實際移動檔案")
    parser.add_argument(
        "--report",
        default=None,
        help="重複檔案報表輸出路徑（預設: output_folder/duplicates_report.csv）",
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
        "--keep-strategy",
        default="folder1",
        choices=["folder1", "folder2", "latest", "earliest", "prefer-path"],
        help="重複檔案保留策略（預設: folder1）",
    )
    parser.add_argument(
        "--prefer-path",
        default=None,
        help="保留策略為 prefer-path 時的路徑前綴",
    )
    parser.add_argument(
        "--move-scope",
        default="folder2",
        choices=["folder2", "both"],
        help="移動範圍（預設: folder2，只移動 folder2 的檔案）",
    )

    args = parser.parse_args()

    if args.keep_strategy == "prefer-path" and not args.prefer_path:
        print("錯誤: keep-strategy=prefer-path 時必須提供 --prefer-path")
        return

    # 檢查資料夾是否存在
    if not os.path.isdir(args.folder1):
        print(f"錯誤: 資料夾不存在 - {args.folder1}")
        return
    if not os.path.isdir(args.folder2):
        print(f"錯誤: 資料夾不存在 - {args.folder2}")
        return

    # 檢查資料夾是否重疊
    overlap = check_overlapping_folders(args.folder1, args.folder2)
    if overlap == 'same':
        print("錯誤: folder1 和 folder2 是同一個資料夾")
        return
    if overlap == 'folder1_contains_folder2':
        print("警告: folder2 是 folder1 的子資料夾，可能導致非預期的結果")
        response = input("是否繼續？(y/N): ").strip().lower()
        if response != 'y':
            print("已取消")
            return
    if overlap == 'folder2_contains_folder1':
        print("警告: folder1 是 folder2 的子資料夾，可能導致非預期的結果")
        response = input("是否繼續？(y/N): ").strip().lower()
        if response != 'y':
            print("已取消")
            return

    files1 = scan_folder(args.folder1, args.recursive)
    files2 = scan_folder(args.folder2, args.recursive)

    print(f"資料夾 1: {len(files1)} 個檔案")
    print(f"資料夾 2: {len(files2)} 個檔案")

    matches = find_duplicates_between(
        files1,
        files2,
        partial_bytes=max(args.partial_size_mb, 1) * 1024 * 1024,
        full_hash_algo=args.full_hash,
    )

    if not matches:
        print("沒有找到重複檔案")
    else:
        print(f"找到 {len(matches)} 個重複檔案")

    moved_count, operations = move_duplicates(
        matches,
        args.output,
        dry_run=args.dry_run,
        keep_strategy=args.keep_strategy,
        prefer_path=args.prefer_path,
        move_scope=args.move_scope,
    )

    for op in operations:
        if op.action == "kept_by_strategy":
            print(f"[保留] {op.keep_path} (策略: {op.strategy})")
            continue
        if op.keep_path == op.duplicate.path:
            src = op.original.path
        else:
            src = op.duplicate.path
        if args.dry_run:
            print(f"[預覽] 將移動: {src} -> {op.move_path}")
        else:
            print(f"已移動: {src} -> {op.move_path}")

    report_path = args.report or os.path.join(args.output, "duplicates_report.csv")
    write_duplicates_report(matches, report_path, actions=operations)
    print(f"報表已輸出: {report_path}")

    if not args.dry_run:
        print(f"共移動 {moved_count} 個重複檔案")


if __name__ == "__main__":
    main()
