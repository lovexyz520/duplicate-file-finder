from __future__ import annotations

from core.dupe import find_duplicates_between, group_duplicates, pick_keep_for_group
from core.scanner import scan_folder

PARTIAL = 1024 * 1024


def _make(tmp_path, name, content: bytes, subdir=""):
    folder = tmp_path / subdir if subdir else tmp_path
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_bytes(content)
    return p


class TestFindDuplicatesBetween:
    def test_finds_identical_files(self, tmp_path):
        _make(tmp_path, "a.bin", b"hello world", "f1")
        _make(tmp_path, "b.bin", b"hello world", "f2")
        files1 = scan_folder(str(tmp_path / "f1"))
        files2 = scan_folder(str(tmp_path / "f2"))
        matches = find_duplicates_between(files1, files2, PARTIAL)
        assert len(matches) == 1

    def test_different_content_same_size_no_match(self, tmp_path):
        _make(tmp_path, "a.bin", b"aaaa", "f1")
        _make(tmp_path, "b.bin", b"bbbb", "f2")
        files1 = scan_folder(str(tmp_path / "f1"))
        files2 = scan_folder(str(tmp_path / "f2"))
        assert find_duplicates_between(files1, files2, PARTIAL) == []

    def test_same_file_not_matched_with_itself(self, tmp_path):
        _make(tmp_path, "a.bin", b"data", "f1")
        files1 = scan_folder(str(tmp_path / "f1"))
        assert find_duplicates_between(files1, files1, PARTIAL) == []

    def test_progress_callback_called(self, tmp_path):
        _make(tmp_path, "a.bin", b"hello", "f1")
        _make(tmp_path, "b.bin", b"hello", "f2")
        files1 = scan_folder(str(tmp_path / "f1"))
        files2 = scan_folder(str(tmp_path / "f2"))
        calls = []
        find_duplicates_between(
            files1, files2, PARTIAL, progress=lambda d, t: calls.append((d, t))
        )
        assert calls
        assert calls[-1][0] == calls[-1][1]


class TestGroupDuplicates:
    def test_groups_identical(self, tmp_path):
        _make(tmp_path, "a.bin", b"same")
        _make(tmp_path, "b.bin", b"same")
        _make(tmp_path, "c.bin", b"diff")
        files = scan_folder(str(tmp_path))
        groups = group_duplicates(files, PARTIAL)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_returns_hashes(self, tmp_path):
        _make(tmp_path, "a.bin", b"same")
        _make(tmp_path, "b.bin", b"same")
        files = scan_folder(str(tmp_path))
        groups = group_duplicates(files, PARTIAL)
        for grouped in groups[0]:
            assert grouped.partial_hash
            assert grouped.full_hash
        assert groups[0][0].full_hash == groups[0][1].full_hash

    def test_no_duplicates(self, tmp_path):
        _make(tmp_path, "a.bin", b"one")
        _make(tmp_path, "b.bin", b"twoo")
        files = scan_folder(str(tmp_path))
        assert group_duplicates(files, PARTIAL) == []


class TestPickKeepForGroup:
    def test_latest(self, tmp_path):
        import os

        a = _make(tmp_path, "a.bin", b"x")
        b = _make(tmp_path, "b.bin", b"x")
        os.utime(a, (1000, 1000))
        os.utime(b, (2000, 2000))
        files = scan_folder(str(tmp_path))
        keep = pick_keep_for_group(files, "latest", None)
        assert keep.path == str(b)

    def test_prefer_path(self, tmp_path):
        _make(tmp_path, "a.bin", b"x", "keep_here")
        _make(tmp_path, "b.bin", b"x", "other")
        files = scan_folder(str(tmp_path), recursive=True)
        keep = pick_keep_for_group(files, "prefer-path", str(tmp_path / "keep_here"))
        assert "keep_here" in keep.path
