from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Iterable

# 統一操作 log 格式（JSONL），供所有模式與 Undo 使用。
# 每筆 record 必要欄位：
#   op:     "move" | "copy" | "trash"
#   source: 原始路徑
#   dest:   目的路徑（trash 為 None）
#   status: "moved" | "copied" | "trashed" | "failed"
#   kind:   "duplicate" | "organize" | "pair" | "photo" | ...
# 其餘欄位為各模式自由附加的 metadata。


def make_record(
    op: str,
    source: str,
    dest: str | None,
    status: str,
    kind: str,
    error: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "op": op,
        "source": source,
        "dest": dest,
        "status": status,
        "kind": kind,
    }
    if error:
        record["error"] = error
    record.update(extra)
    return record


def default_log_path(output_folder: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(output_folder, f"actions_log_{stamp}.jsonl")


def write_oplog(records: Iterable[dict[str, Any]], log_path: str) -> None:
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "op": "meta",
                    "created_at": datetime.now().isoformat(),
                    "version": 1,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_oplog(log_path: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("op") == "meta":
                continue
            records.append(record)
    return records
