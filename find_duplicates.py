"""
Duplicate File Finder - 重複檔案搜尋工具

比對兩個資料夾，找出並移動重複的檔案。

運作流程：
1. 掃描兩個資料夾中的檔案
2. 先比對檔案大小，大小不同則跳過（效能優化）
3. 先做 partial hash（前/後 1MB 的 xxhash）
4. partial hash 相同時做完整 SHA256
5. 將 folder2 中的重複檔案移動到輸出資料夾（或資源回收桶）

使用方式：
    uv run find_duplicates.py [folder1] [folder2] [-o OUTPUT] [-r] [--dry-run]
        [--partial-size-mb N] [--full-hash sha256|xxhash64]
        [--keep-strategy folder1|folder2|latest|earliest|prefer-path]
        [--prefer-path PATH] [--move-scope folder2|both]
        [--to-trash] [--min-size-kb N] [--exclude-dirs a,b] [--no-hidden]

執行後會輸出 actions_log_*.jsonl，可用 undo_actions.py 還原。
"""

from __future__ import annotations

import argparse
import os

from core import (
    check_overlapping,
    default_log_path,
    duplicate_actions_to_records,
    find_duplicates_between,
    move_duplicates,
    scan_folder,
    write_duplicates_report,
    write_oplog,
)

# 預設資料夾路徑
DEFAULT_FOLDER1 = 'folder1'
DEFAULT_FOLDER2 = 'folder2'
DEFAULT_OUTPUT = 'output_folder'


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
    parser.add_argument(
        "--to-trash",
        action="store_true",
        help="重複檔案移到資源回收桶（取代移到輸出資料夾）",
    )
    parser.add_argument(
        "--min-size-kb",
        type=int,
        default=0,
        help="略過小於此大小的檔案（KB，預設: 0 = 不過濾）",
    )
    parser.add_argument(
        "--exclude-dirs",
        default="",
        help="排除的資料夾名稱（逗號分隔，例：.git,node_modules）",
    )
    parser.add_argument(
        "--no-hidden",
        action="store_true",
        help="略過隱藏檔案與資料夾（以 . 開頭）",
    )
    parser.add_argument(
        "--clean-names",
        action="store_true",
        help="啟用檔名清理（包含移除(1)/(2)、空白正規化、移除特殊字元、衝突補 _001）",
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
    overlap = check_overlapping(args.folder1, args.folder2)
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

    exclude_dirs = {d.strip() for d in args.exclude_dirs.split(",") if d.strip()} or None
    scan_kwargs = dict(
        min_size=args.min_size_kb * 1024,
        include_hidden=not args.no_hidden,
        exclude_dirs=exclude_dirs,
    )
    files1 = scan_folder(args.folder1, args.recursive, **scan_kwargs)
    files2 = scan_folder(args.folder2, args.recursive, **scan_kwargs)

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

    moved_count, operations = move_duplicates(
        matches,
        args.output,
        dry_run=args.dry_run,
        keep_strategy=args.keep_strategy,
        prefer_path=args.prefer_path,
        move_scope=args.move_scope,
        clean_names=clean_enabled,
        clean_copy_suffix=clean_copy_suffix,
        clean_normalize_space=clean_normalize_space,
        clean_remove_special=clean_remove_special,
        conflict_suffix_width=conflict_width,
        to_trash=args.to_trash,
    )

    moves: list[tuple[str, str]] = []
    keeps: list[str] = []
    conflicts: list[tuple[str, str, str]] = []
    failures: list[tuple[str, str]] = []

    for op in operations:
        if op.action == "kept_by_strategy":
            keeps.append(op.keep_path)
            continue

        if op.keep_path == op.duplicate.path:
            src = op.original.path
        else:
            src = op.duplicate.path

        if op.action == "failed":
            failures.append((src, op.error or ""))
            continue

        dest = op.move_path or ("(資源回收桶)" if args.to_trash else "")
        moves.append((src, dest))
        if op.name_conflict and op.desired_move_path:
            conflicts.append((src, op.desired_move_path, op.move_path or ""))

    if keeps:
        print("\n保留清單:")
        for path in keeps:
            print(f"[保留] {path} (策略: {args.keep_strategy})")

    if moves:
        print("\n移動清單:")
        for src, dest in moves:
            if args.dry_run:
                print(f"[預覽] 將移動: {src} -> {dest}")
            else:
                print(f"已移動: {src} -> {dest}")

    if conflicts:
        print("\n檔名衝突清單:")
        for src, desired, final in conflicts:
            print(f"[衝突] {src} -> {desired} (改名為 {final})")

    if failures:
        print("\n失敗清單:")
        for src, error in failures:
            print(f"[失敗] {src}: {error}")

    report_path = args.report or os.path.join(args.output, "duplicates_report.csv")
    if not args.dry_run:
        write_duplicates_report(matches, report_path, actions=operations)
        print(f"報表已輸出: {report_path}")

        log_path = default_log_path(args.output)
        write_oplog(duplicate_actions_to_records(operations), log_path)
        print(f"操作 log: {log_path}")
        print(f"還原指令: uv run undo_actions.py \"{log_path}\"")

    kept_count = len(keeps)
    move_count = len(moves)
    conflict_count = len(conflicts)
    print(
        f"\n摘要: 重複檔案 {len(matches)} 個，"
        f"保留 {kept_count} 個，"
        f"{'預覽移動' if args.dry_run else '移動'} {move_count} 個，"
        f"命名衝突 {conflict_count} 個，"
        f"失敗 {len(failures)} 個"
    )

    if not args.dry_run:
        print(f"共處理 {moved_count} 個重複檔案")


if __name__ == "__main__":
    main()
