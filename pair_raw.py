from __future__ import annotations

import argparse
import os

from core import (
    JPG_EXTS_DEFAULT,
    RAW_EXTS_DEFAULT,
    default_log_path,
    execute_pair_actions,
    pair_actions_to_records,
    pair_by_stem,
    plan_pair_layout,
    write_oplog,
    write_pairs_report,
)


def _parse_exts(exts: str) -> set[str]:
    values = {e.strip().lower() for e in exts.split(",") if e.strip()}
    if not values:
        return set()
    normalized = set()
    for ext in values:
        normalized.add(ext if ext.startswith(".") else f".{ext}")
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JPG/RAW 配對工具（支援配對複製與成對整理）"
    )
    parser.add_argument("jpg_folder", help="JPG 資料夾")
    parser.add_argument("raw_folder", help="RAW 資料夾")
    parser.add_argument("-o", "--output", default="pair_output", help="輸出資料夾")
    parser.add_argument(
        "--mode",
        default="copy-raw",
        choices=["copy-raw", "pair-organize"],
        help="模式：copy-raw（僅複製 RAW）或 pair-organize（成對整理）",
    )
    parser.add_argument("-r", "--recursive", action="store_true", help="遞迴掃描子資料夾")
    parser.add_argument(
        "--raw-exts",
        default="",
        help="RAW 副檔名清單（逗號分隔，例：.ARW,.CR2）",
    )
    parser.add_argument(
        "--jpg-exts",
        default="",
        help="JPG 副檔名清單（逗號分隔，例：.JPG,.JPEG,.HEIC）",
    )
    parser.add_argument(
        "--key-mode",
        default="stem",
        choices=["stem", "stem+parent"],
        help="配對 key 模式（stem 或 stem+parent）",
    )
    parser.add_argument(
        "--layout",
        default="raw-with-jpg",
        choices=["raw-with-jpg", "per-pair-folder", "split-index"],
        help="成對整理的布局模式",
    )
    parser.add_argument("--dry-run", action="store_true", help="預覽，不實際複製/移動")
    parser.add_argument("--move", action="store_true", help="成對整理時用移動而非複製")

    args = parser.parse_args()

    if not os.path.isdir(args.jpg_folder):
        print(f"錯誤：JPG 資料夾不存在 - {args.jpg_folder}")
        return
    if not os.path.isdir(args.raw_folder):
        print(f"錯誤：RAW 資料夾不存在 - {args.raw_folder}")
        return

    jpg_exts = _parse_exts(args.jpg_exts) or JPG_EXTS_DEFAULT
    raw_exts = _parse_exts(args.raw_exts) or RAW_EXTS_DEFAULT

    pairs, orphan_jpgs, orphan_raws = pair_by_stem(
        args.jpg_folder,
        args.raw_folder,
        recursive=args.recursive,
        jpg_exts=jpg_exts,
        raw_exts=raw_exts,
        key_mode=args.key_mode,
    )

    print(f"配對成功：{len(pairs)}")
    print(f"孤兒 JPG：{len(orphan_jpgs)}")
    print(f"孤兒 RAW：{len(orphan_raws)}")

    if not args.dry_run:
        report_pairs = os.path.join(args.output, "pairs.csv")
        report_orphans = os.path.join(args.output, "orphans.csv")
        write_pairs_report(pairs, orphan_jpgs, orphan_raws, report_pairs, report_orphans)
        print(f"報表輸出：{report_pairs}")
        print(f"報表輸出：{report_orphans}")

    if args.mode == "copy-raw":
        actions = plan_pair_layout(
            pairs,
            args.output,
            layout="raw-with-jpg",
            action="copy",
            conflict_suffix_width=3,
        )
        actions = [a for a in actions if a.role == "raw"]
        use_move = False
        verb = "RAW 複製"
    else:
        actions = plan_pair_layout(
            pairs,
            args.output,
            layout=args.layout,
            action="move" if args.move else "copy",
            conflict_suffix_width=3,
        )
        use_move = args.move
        verb = "成對整理"

    copied, completed = execute_pair_actions(
        actions,
        dry_run=args.dry_run,
        move=use_move,
    )

    failures = [a for a in completed if a.action == "failed"]
    if failures:
        print(f"\n失敗 {len(failures)} 筆:")
        for a in failures:
            print(f"[失敗] {a.src_path}: {a.error}")

    if not args.dry_run:
        log_path = default_log_path(args.output)
        write_oplog(pair_actions_to_records(completed, move=use_move), log_path)
        print(f"操作 log: {log_path}")
        print(f"還原指令: uv run undo_actions.py \"{log_path}\"")

    print(f"{'預覽' if args.dry_run else '完成'} {verb}：{copied}，失敗 {len(failures)}")


if __name__ == "__main__":
    main()
