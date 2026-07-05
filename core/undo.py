from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, replace
from typing import Any, Callable

from .oplog import read_oplog

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class UndoAction:
    op: str  # 原始操作："move" | "copy" | "trash"
    source: str  # 原始來源（還原目的地）
    dest: str | None  # 原始目的地（還原來源）
    kind: str
    status: str  # "preview" | "restored" | "removed_copy" | "skipped" | "failed"
    reason: str | None = None


def plan_undo(records: list[dict[str, Any]]) -> list[UndoAction]:
    """從操作 log 規劃還原動作（反向、後進先出）。

    檔案存在性在執行階段才檢查：鏈式移動（a→b→c）要先還原 c→b，
    b 才會存在，規劃當下檢查會誤判。
    """
    actions: list[UndoAction] = []
    for record in reversed(records):
        op = record.get("op", "")
        source = record.get("source", "")
        dest = record.get("dest")
        kind = record.get("kind", "")
        status = record.get("status", "")

        if status == "failed":
            actions.append(
                UndoAction(op, source, dest, kind, "skipped", "原操作已失敗，無需還原")
            )
            continue
        if op == "trash":
            actions.append(
                UndoAction(op, source, dest, kind, "skipped", "資源回收桶項目請手動還原")
            )
            continue
        if op not in {"move", "copy"} or not dest:
            actions.append(UndoAction(op, source, dest, kind, "skipped", "無法識別的操作"))
            continue
        actions.append(UndoAction(op, source, dest, kind, "preview"))
    return actions


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def execute_undo(
    actions: list[UndoAction],
    dry_run: bool = False,
    progress: ProgressCallback | None = None,
) -> list[UndoAction]:
    completed: list[UndoAction] = []
    total = len(actions)
    # 模擬檔案系統狀態，dry-run 與鏈式還原都靠它判斷存在性
    appeared: set[str] = set()
    removed: set[str] = set()

    def _exists(path: str) -> bool:
        key = _norm(path)
        if key in removed:
            return False
        if key in appeared:
            return True
        return os.path.exists(path)

    for index, action in enumerate(actions, start=1):
        if progress:
            progress(index, total)
        if action.status != "preview":
            completed.append(action)
            continue

        dest = action.dest or ""
        if not _exists(dest):
            completed.append(
                replace(action, status="skipped", reason="目的檔案已不存在")
            )
            continue
        if action.op == "move" and _exists(action.source):
            completed.append(
                replace(action, status="skipped", reason="原始位置已有同名檔案")
            )
            continue

        try:
            if not dry_run:
                if action.op == "move":
                    os.makedirs(os.path.dirname(action.source), exist_ok=True)
                    shutil.move(dest, action.source)
                else:  # copy：移除副本即可
                    os.remove(dest)
            removed.add(_norm(dest))
            if action.op == "move":
                appeared.add(_norm(action.source))
            if dry_run:
                completed.append(action)
            else:
                completed.append(
                    replace(
                        action,
                        status="restored" if action.op == "move" else "removed_copy",
                    )
                )
        except Exception as exc:  # noqa: BLE001 - 逐檔隔離錯誤
            completed.append(replace(action, status="failed", reason=str(exc)))
    return completed


def undo_from_log(
    log_path: str,
    dry_run: bool = False,
    progress: ProgressCallback | None = None,
) -> list[UndoAction]:
    records = read_oplog(log_path)
    actions = plan_undo(records)
    return execute_undo(actions, dry_run=dry_run, progress=progress)
