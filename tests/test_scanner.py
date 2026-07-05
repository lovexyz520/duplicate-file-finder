from __future__ import annotations

from core.paths import check_overlapping
from core.scanner import scan_folder


class TestScanFilters:
    def test_min_size(self, tmp_path):
        (tmp_path / "small.txt").write_text("x")
        (tmp_path / "big.txt").write_text("x" * 2048)
        files = scan_folder(str(tmp_path), min_size=1024)
        assert [f.path for f in files] == [str(tmp_path / "big.txt")]

    def test_exclude_hidden(self, tmp_path):
        (tmp_path / ".hidden.txt").write_text("x")
        (tmp_path / "visible.txt").write_text("x")
        files = scan_folder(str(tmp_path), include_hidden=False)
        assert len(files) == 1
        assert files[0].path.endswith("visible.txt")

    def test_exclude_dirs_recursive(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.js").write_text("x")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("x")
        files = scan_folder(str(tmp_path), recursive=True, exclude_dirs={"node_modules"})
        assert len(files) == 1
        assert files[0].path.endswith("main.py")

    def test_exclude_dirs_case_insensitive(self, tmp_path):
        (tmp_path / "Node_Modules").mkdir()
        (tmp_path / "Node_Modules" / "pkg.js").write_text("x")
        files = scan_folder(str(tmp_path), recursive=True, exclude_dirs={"node_modules"})
        assert files == []


class TestCheckOverlapping:
    def test_same(self, tmp_path):
        assert check_overlapping(str(tmp_path), str(tmp_path)) == "same"

    def test_same_different_case(self, tmp_path):
        assert check_overlapping(str(tmp_path).upper(), str(tmp_path).lower()) == "same"

    def test_containment(self, tmp_path):
        child = tmp_path / "sub"
        child.mkdir()
        assert check_overlapping(str(tmp_path), str(child)) == "folder1_contains_folder2"
        assert check_overlapping(str(child), str(tmp_path)) == "folder2_contains_folder1"

    def test_no_overlap_similar_prefix(self, tmp_path):
        a = tmp_path / "foo"
        b = tmp_path / "foobar"
        a.mkdir()
        b.mkdir()
        assert check_overlapping(str(a), str(b)) is None
