from __future__ import annotations

import os

from core.actions import move_duplicates
from core.dupe import find_duplicates_between
from core.scanner import scan_folder

PARTIAL = 1024 * 1024


def _setup_dupes(tmp_path):
    f1 = tmp_path / "f1"
    f2 = tmp_path / "f2"
    f1.mkdir()
    f2.mkdir()
    (f1 / "a.bin").write_bytes(b"same-content")
    (f2 / "a.bin").write_bytes(b"same-content")
    files1 = scan_folder(str(f1))
    files2 = scan_folder(str(f2))
    return find_duplicates_between(files1, files2, PARTIAL)


class TestMoveDuplicates:
    def test_dry_run_does_not_touch_disk(self, tmp_path):
        matches = _setup_dupes(tmp_path)
        out = tmp_path / "out"
        moved, ops = move_duplicates(matches, str(out), dry_run=True)
        assert moved == 0
        assert not out.exists()
        assert all(op.action == "preview" for op in ops)

    def test_execute_moves_duplicate(self, tmp_path):
        matches = _setup_dupes(tmp_path)
        out = tmp_path / "out"
        moved, ops = move_duplicates(matches, str(out), dry_run=False)
        assert moved == 1
        assert (out / "a.bin").exists()
        assert not (tmp_path / "f2" / "a.bin").exists()
        assert (tmp_path / "f1" / "a.bin").exists()

    def test_same_name_duplicates_get_distinct_destinations(self, tmp_path):
        """兩個同名重複檔不能解析到同一目的地（覆蓋 bug 回歸測試）。"""
        f1 = tmp_path / "f1"
        f2a = tmp_path / "f2" / "sub1"
        f2b = tmp_path / "f2" / "sub2"
        for d in (f1, f2a, f2b):
            d.mkdir(parents=True)
        (f1 / "x.bin").write_bytes(b"content-1")
        (f1 / "y.bin").write_bytes(b"content-2!")
        (f2a / "same.bin").write_bytes(b"content-1")
        (f2b / "same.bin").write_bytes(b"content-2!")

        files1 = scan_folder(str(f1))
        files2 = scan_folder(str(tmp_path / "f2"), recursive=True)
        matches = find_duplicates_between(files1, files2, PARTIAL)
        assert len(matches) == 2

        moved, ops = move_duplicates(matches, str(tmp_path / "out"), dry_run=True)
        dests = [op.move_path for op in ops if op.move_path]
        assert len(dests) == len(set(dests)), "同名檔案解析到相同目的地"

    def test_failed_file_does_not_abort_batch(self, tmp_path, monkeypatch):
        f1 = tmp_path / "f1"
        f2 = tmp_path / "f2"
        f1.mkdir()
        f2.mkdir()
        (f1 / "a.bin").write_bytes(b"AAA-content")
        (f2 / "a.bin").write_bytes(b"AAA-content")
        (f1 / "b.bin").write_bytes(b"BBB-content")
        (f2 / "b.bin").write_bytes(b"BBB-content")
        matches = find_duplicates_between(
            scan_folder(str(f1)), scan_folder(str(f2)), PARTIAL
        )
        assert len(matches) == 2

        import shutil

        real_move = shutil.move
        calls = {"n": 0}

        def flaky_move(src, dst, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("simulated failure")
            return real_move(src, dst, **kwargs)

        monkeypatch.setattr("core.actions.shutil.move", flaky_move)
        moved, ops = move_duplicates(matches, str(tmp_path / "out"), dry_run=False)
        assert moved == 1
        statuses = sorted(op.action for op in ops)
        assert statuses == ["failed", "moved"]
        failed = [op for op in ops if op.action == "failed"][0]
        assert "simulated failure" in (failed.error or "")

    def test_keep_strategy_latest(self, tmp_path):
        matches = _setup_dupes(tmp_path)
        os.utime(tmp_path / "f1" / "a.bin", (1000, 1000))
        os.utime(tmp_path / "f2" / "a.bin", (2000, 2000))
        # rescan for updated mtimes
        matches = find_duplicates_between(
            scan_folder(str(tmp_path / "f1")),
            scan_folder(str(tmp_path / "f2")),
            PARTIAL,
        )
        moved, ops = move_duplicates(
            matches, str(tmp_path / "out"), dry_run=True, keep_strategy="latest"
        )
        assert ops[0].action == "kept_by_strategy"
        assert ops[0].keep_path == str(tmp_path / "f2" / "a.bin")
