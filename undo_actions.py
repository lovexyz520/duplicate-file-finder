"""
Undo Actions - 操作還原工具

讀取執行後輸出的 actions_log_*.jsonl，反向還原操作：
- moved（移動）：把檔案從目的地搬回原始位置
- copied（複製）：刪除複製出來的副本
- trashed（資源回收桶）：無法自動還原，請手動處理

使用方式：
    uv run undo_actions.py <log_path> [--dry-run]
"""

from __future__ import annotations

import argparse
import os

from core import execute_undo, plan_undo, read_oplog


def main() -> None:
    parser = argparse.ArgumentParser(description="從操作 log 還原檔案")
    parser.add_argument("log_path", help="actions_log_*.jsonl 路徑")
    parser.add_argument("--dry-run", action="store_true", help="預覽，不實際還原")

    args = parser.parse_args()

    if not os.path.isfile(args.log_path):
        print(f"錯誤: log 檔不存在 - {args.log_path}")
        return

    records = read_oplog(args.log_path)
    print(f"讀取 {len(records)} 筆操作記錄")

    actions = plan_undo(records)
    results = execute_undo(actions, dry_run=args.dry_run)

    restored = 0
    removed = 0
    skipped = 0
    failed = 0
    for action in results:
        if action.status == "restored":
            restored += 1
            print(f"[還原] {action.dest} -> {action.source}")
        elif action.status == "removed_copy":
            removed += 1
            print(f"[刪除副本] {action.dest}")
        elif action.status == "preview":
            verb = "搬回" if action.op == "move" else "刪除副本"
            print(f"[預覽] 將{verb}: {action.dest}")
        elif action.status == "skipped":
            skipped += 1
            print(f"[略過] {action.dest or action.source}: {action.reason}")
        elif action.status == "failed":
            failed += 1
            print(f"[失敗] {action.dest}: {action.reason}")

    if args.dry_run:
        pending = sum(1 for a in results if a.status == "preview")
        print(f"\n摘要（預覽）: 可還原 {pending} 筆，略過 {skipped} 筆")
    else:
        print(
            f"\n摘要: 還原 {restored} 筆，刪除副本 {removed} 筆，"
            f"略過 {skipped} 筆，失敗 {failed} 筆"
        )


if __name__ == "__main__":
    main()
