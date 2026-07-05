from __future__ import annotations

import os

from core.organizer import organize


def _fill_source(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "doc.txt").write_text("text file")
    (src / "pic.jpg").write_bytes(b"fake-jpg-data")
    (src / "dupe1.bin").write_bytes(b"identical-content")
    (src / "dupe2.bin").write_bytes(b"identical-content")
    return src


class TestOrganizeDryRun:
    def test_dry_run_has_no_side_effects(self, tmp_path):
        src = _fill_source(tmp_path)
        out = tmp_path / "out"
        total, dupes, dupe_actions, org_actions = organize(
            str(src), str(out), dry_run=True
        )
        assert total == 4
        assert not out.exists(), "dry-run 不應建立輸出資料夾"
        assert all(a.action == "preview" for a in org_actions)
        # 來源檔案完好
        assert (src / "dupe1.bin").exists()
        assert (src / "dupe2.bin").exists()

    def test_dry_run_detects_duplicates(self, tmp_path):
        src = _fill_source(tmp_path)
        _, dupes, _, _ = organize(str(src), str(tmp_path / "out"), dry_run=True)
        assert len(dupes) == 1


class TestOrganizeExecute:
    def test_moves_files_into_categories(self, tmp_path):
        src = _fill_source(tmp_path)
        out = tmp_path / "out"
        total, dupes, dupe_actions, org_actions = organize(
            str(src), str(out), dry_run=False
        )
        assert (out / "Docs" / "doc.txt").exists()
        assert (out / "Images" / "pic.jpg").exists()
        # 一份重複檔進 Duplicates，一份留下被整理
        dupe_files = list((out / "Duplicates").glob("*.bin"))
        assert len(dupe_files) == 1
        assert (out / "organize_report.csv").exists()

    def test_time_partition(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        f = src / "doc.txt"
        f.write_text("x")
        os.utime(f, (1704067200, 1704067200))  # 2024-01-01 UTC
        out = tmp_path / "out"
        organize(str(src), str(out), dry_run=False, time_partition=True, skip_duplicates=True)
        month_dirs = [p.name for p in out.iterdir() if p.is_dir()]
        assert any(d.startswith("202") for d in month_dirs)

    def test_min_size_filter(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "small.txt").write_text("x")
        (src / "big.txt").write_text("x" * 5000)
        total, _, _, actions = organize(
            str(src), str(tmp_path / "out"), dry_run=True, skip_duplicates=True,
            min_size=1000,
        )
        assert total == 1

    def test_exclude_dirs(self, tmp_path):
        src = tmp_path / "src"
        (src / ".git").mkdir(parents=True)
        (src / ".git" / "config").write_text("x")
        (src / "doc.txt").write_text("y")
        total, _, _, _ = organize(
            str(src), str(tmp_path / "out"), recursive=True, dry_run=True,
            skip_duplicates=True, exclude_dirs={".git"},
        )
        assert total == 1
