from __future__ import annotations

from core.naming import DestinationResolver, clean_filename, safe_key_folder


class TestCleanFilename:
    def test_remove_copy_suffix(self):
        assert clean_filename("photo (1).jpg", True, False, False) == "photo.jpg"
        assert clean_filename("photo (23).jpg", True, False, False) == "photo.jpg"

    def test_normalize_space(self):
        assert clean_filename("a  b　c.txt", False, True, False) == "a b c.txt"

    def test_remove_special(self):
        assert clean_filename("a@b#c!.txt", False, False, True) == "abc.txt"

    def test_empty_stem_fallback(self):
        assert clean_filename("(1).txt", True, False, False) == "file.txt"


class TestDestinationResolver:
    def test_no_conflict(self, tmp_path):
        resolver = DestinationResolver()
        desired, dest, conflict = resolver.resolve(str(tmp_path), "a.txt", 3)
        assert desired == dest
        assert not conflict

    def test_conflict_with_existing_file(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        resolver = DestinationResolver()
        _, dest, conflict = resolver.resolve(str(tmp_path), "a.txt", 3)
        assert conflict
        assert dest.endswith("a_001.txt")

    def test_conflict_with_reserved_path(self, tmp_path):
        """同一批計畫中兩個同名檔案不能解析到同一個目的地（覆蓋 bug 回歸測試）。"""
        resolver = DestinationResolver()
        _, dest1, conflict1 = resolver.resolve(str(tmp_path), "a.txt", 3)
        _, dest2, conflict2 = resolver.resolve(str(tmp_path), "a.txt", 3)
        assert not conflict1
        assert conflict2
        assert dest1 != dest2
        assert dest2.endswith("a_001.txt")

    def test_reserved_case_insensitive(self, tmp_path):
        resolver = DestinationResolver()
        _, dest1, _ = resolver.resolve(str(tmp_path), "A.txt", 3)
        _, dest2, _ = resolver.resolve(str(tmp_path), "a.txt", 3)
        assert dest1.lower() != dest2.lower()

    def test_zero_width_suffix(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        resolver = DestinationResolver()
        _, dest, _ = resolver.resolve(str(tmp_path), "a.txt", 0)
        assert dest.endswith("a_1.txt")


def test_safe_key_folder():
    assert safe_key_folder("dsc-001") == "dsc-001"
    assert safe_key_folder("a/b:c") == "a_b_c"
    assert safe_key_folder("///") == "pair"
