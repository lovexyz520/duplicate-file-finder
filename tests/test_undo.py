from __future__ import annotations

import os

from core.oplog import make_record, read_oplog, write_oplog
from core.undo import execute_undo, plan_undo, undo_from_log


class TestOplog:
    def test_roundtrip(self, tmp_path):
        records = [
            make_record("move", "a", "b", "moved", "organize", category="Docs"),
            make_record("copy", "c", "d", "copied", "pair"),
        ]
        log_path = str(tmp_path / "log.jsonl")
        write_oplog(records, log_path)
        loaded = read_oplog(log_path)
        assert len(loaded) == 2
        assert loaded[0]["op"] == "move"
        assert loaded[0]["category"] == "Docs"


class TestUndo:
    def test_undo_move(self, tmp_path):
        src = tmp_path / "original" / "a.txt"
        dest = tmp_path / "moved" / "a.txt"
        dest.parent.mkdir()
        dest.write_text("data")

        records = [make_record("move", str(src), str(dest), "moved", "organize")]
        actions = plan_undo(records)
        results = execute_undo(actions)
        assert results[0].status == "restored"
        assert src.exists()
        assert not dest.exists()

    def test_undo_copy_removes_duplicate(self, tmp_path):
        src = tmp_path / "a.txt"
        dest = tmp_path / "copy" / "a.txt"
        src.write_text("data")
        dest.parent.mkdir()
        dest.write_text("data")

        records = [make_record("copy", str(src), str(dest), "copied", "pair")]
        results = execute_undo(plan_undo(records))
        assert results[0].status == "removed_copy"
        assert src.exists()
        assert not dest.exists()

    def test_undo_skips_when_source_occupied(self, tmp_path):
        src = tmp_path / "a.txt"
        dest = tmp_path / "moved" / "a.txt"
        src.write_text("newer file took the spot")
        dest.parent.mkdir()
        dest.write_text("data")

        records = [make_record("move", str(src), str(dest), "moved", "organize")]
        results = execute_undo(plan_undo(records))
        assert results[0].status == "skipped"
        assert dest.exists()

    def test_undo_skips_missing_dest(self, tmp_path):
        records = [
            make_record(
                "move",
                str(tmp_path / "a.txt"),
                str(tmp_path / "gone.txt"),
                "moved",
                "organize",
            )
        ]
        results = execute_undo(plan_undo(records))
        assert results[0].status == "skipped"

    def test_undo_skips_trash(self, tmp_path):
        records = [make_record("trash", str(tmp_path / "a.txt"), None, "trashed", "duplicate")]
        results = execute_undo(plan_undo(records))
        assert results[0].status == "skipped"

    def test_dry_run_does_not_restore(self, tmp_path):
        src = tmp_path / "a.txt"
        dest = tmp_path / "moved.txt"
        dest.write_text("data")
        records = [make_record("move", str(src), str(dest), "moved", "organize")]
        log_path = str(tmp_path / "log.jsonl")
        write_oplog(records, log_path)
        results = undo_from_log(log_path, dry_run=True)
        assert results[0].status == "preview"
        assert dest.exists()
        assert not src.exists()

    def test_undo_reverse_order(self, tmp_path):
        """後執行的操作先還原（鏈式移動 a→b→c 才能正確還原）。"""
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        c = tmp_path / "c.txt"
        c.write_text("data")
        records = [
            make_record("move", str(a), str(b), "moved", "organize"),
            make_record("move", str(b), str(c), "moved", "organize"),
        ]
        results = execute_undo(plan_undo(records))
        assert a.exists()
        assert not b.exists()
        assert not c.exists()
        assert all(r.status == "restored" for r in results)
