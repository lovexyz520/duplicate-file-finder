from __future__ import annotations

import argparse
import os

from core import (
    PairRecord,
    execute_duplicate_actions,
    execute_photo_actions,
    plan_photo_actions,
    write_duplicates_report,
    write_pairs_report,
)
from core import default_log_path, write_actions_log
from rules_presets import PHOTO_PRESET


def main() -> None:
    parser = argparse.ArgumentParser(description="攝影素材整理助手（CLI）")
    parser.add_argument("source", help="來源資料夾")
    parser.add_argument("-o", "--output", default="photo_output", help="輸出資料夾")
    parser.add_argument("-r", "--recursive", action="store_true", help="遞迴掃描")
    parser.add_argument(
        "--layout",
        default="by-date-type",
        choices=["by-date-type", "per-pair-folder"],
        help="輸出布局",
    )
    parser.add_argument(
        "--pair-key",
        default="stem",
        choices=["stem", "stem+parent", "exif"],
        help="成對配對 key",
    )
    parser.add_argument(
        "--disable-duplicates",
        action="store_true",
        help="關閉重複檔案偵測",
    )
    parser.add_argument(
        "--dupe-strategy",
        default="latest",
        choices=["latest", "earliest", "prefer-path"],
        help="重複檔案保留策略",
    )
    parser.add_argument("--prefer-path", default=None, help="保留策略 prefer-path")
    parser.add_argument("--partial-size-mb", type=int, default=1, help="partial hash 大小")
    parser.add_argument(
        "--full-hash",
        default="sha256",
        choices=["sha256", "xxhash64"],
        help="完整 hash 演算法",
    )
    parser.add_argument("--dry-run", action="store_true", help="預覽模式")
    parser.add_argument("--move", action="store_true", help="執行移動（預設複製）")

    args = parser.parse_args()

    if not os.path.isdir(args.source):
        print(f"錯誤：來源資料夾不存在 - {args.source}")
        return

    plan = plan_photo_actions(
        source_folder=args.source,
        output_folder=args.output,
        recursive=args.recursive,
        preset=PHOTO_PRESET,
        layout=args.layout,
        pair_key_mode=args.pair_key,
        enable_duplicates=not args.disable_duplicates,
        dupe_strategy=args.dupe_strategy,
        prefer_path=args.prefer_path,
        partial_size_mb=args.partial_size_mb,
        full_hash_algo=args.full_hash,
        conflict_suffix_width=3,
    )

    print(f"來源檔案數量：{len(plan.media_files)}")
    print(f"配對成功：{len(plan.pairs)}")
    print(f"孤兒 JPG：{len(plan.orphan_jpgs)}")
    print(f"孤兒 RAW：{len(plan.orphan_raws)}")
    print(f"重複檔案：{len(plan.duplicate_matches)}")
    print(f"整理項目：{len(plan.photo_actions)}")

    if args.dry_run:
        print("（預覽模式：未移動檔案、未輸出報表）")
        return

    pairs_path = os.path.join(args.output, "pairs.csv")
    orphans_path = os.path.join(args.output, "orphans.csv")
    pair_records = [PairRecord(key=p[0], jpg_path=p[1], raw_path=p[2]) for p in plan.pairs]
    write_pairs_report(pair_records, plan.orphan_jpgs, plan.orphan_raws, pairs_path, orphans_path)
    print(f"pairs.csv：{pairs_path}")
    print(f"orphans.csv：{orphans_path}")

    completed_duplicates = execute_duplicate_actions(plan.duplicate_actions, dry_run=False)
    completed_actions = execute_photo_actions(
        plan.photo_actions,
        dry_run=False,
        move=args.move,
    )

    if plan.duplicate_matches:
        duplicates_path = os.path.join(args.output, "duplicates_report.csv")
        write_duplicates_report(plan.duplicate_matches, duplicates_path, completed_duplicates)
        print(f"duplicates_report.csv：{duplicates_path}")

    failures = [a for a in completed_actions if a.action == "failed"] + [
        a for a in completed_duplicates if a.action == "failed"
    ]
    if failures:
        print(f"\n失敗 {len(failures)} 筆:")
        for a in failures:
            src = getattr(a, "source_path", None) or a.duplicate.path
            print(f"[失敗] {src}: {a.error}")

    log_path = default_log_path(args.output)
    write_actions_log(completed_actions, completed_duplicates, log_path)
    print(f"操作 log：{log_path}")
    print(f"還原指令: uv run undo_actions.py \"{log_path}\"")


if __name__ == "__main__":
    main()
