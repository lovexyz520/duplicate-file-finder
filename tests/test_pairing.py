from __future__ import annotations

from core.pairing import (
    execute_pair_actions,
    pair_by_stem,
    plan_pair_layout,
    PairRecord,
)


def _setup(tmp_path):
    jpg = tmp_path / "jpg"
    raw = tmp_path / "raw"
    jpg.mkdir()
    raw.mkdir()
    (jpg / "DSC001.jpg").write_bytes(b"jpg1")
    (jpg / "DSC002.jpg").write_bytes(b"jpg2")
    (jpg / "orphan.jpg").write_bytes(b"jpg3")
    (raw / "DSC001.arw").write_bytes(b"raw1")
    (raw / "DSC002.arw").write_bytes(b"raw2")
    (raw / "lonely.arw").write_bytes(b"raw3")
    return jpg, raw


class TestPairByStem:
    def test_pairs_and_orphans(self, tmp_path):
        jpg, raw = _setup(tmp_path)
        pairs, orphan_jpgs, orphan_raws = pair_by_stem(str(jpg), str(raw))
        assert len(pairs) == 2
        assert len(orphan_jpgs) == 1
        assert len(orphan_raws) == 1

    def test_case_insensitive_stem(self, tmp_path):
        jpg = tmp_path / "jpg"
        raw = tmp_path / "raw"
        jpg.mkdir()
        raw.mkdir()
        (jpg / "ABC.jpg").write_bytes(b"1")
        (raw / "abc.arw").write_bytes(b"2")
        pairs, _, _ = pair_by_stem(str(jpg), str(raw))
        assert len(pairs) == 1


class TestPlanPairLayout:
    def test_plan_does_not_touch_disk(self, tmp_path):
        jpg, raw = _setup(tmp_path)
        pairs, _, _ = pair_by_stem(str(jpg), str(raw))
        out = tmp_path / "out"
        plan_pair_layout(pairs, str(out), layout="raw-with-jpg", action="copy")
        assert not out.exists(), "規劃階段不應建立資料夾"

    def test_same_basename_distinct_destinations(self, tmp_path):
        """不同資料夾的同名配對不能覆蓋彼此（覆蓋 bug 回歸測試）。"""
        pairs = [
            PairRecord(key="sub1-dsc001", jpg_path=str(tmp_path / "s1" / "DSC001.jpg"),
                       raw_path=str(tmp_path / "s1" / "DSC001.arw")),
            PairRecord(key="sub2-dsc001", jpg_path=str(tmp_path / "s2" / "DSC001.jpg"),
                       raw_path=str(tmp_path / "s2" / "DSC001.arw")),
        ]
        actions = plan_pair_layout(pairs, str(tmp_path / "out"), layout="raw-with-jpg", action="copy")
        dests = [a.dest_path for a in actions]
        assert len(dests) == len(set(dests)), "同名檔案解析到相同目的地"

    def test_execute_copies_pairs(self, tmp_path):
        jpg, raw = _setup(tmp_path)
        pairs, _, _ = pair_by_stem(str(jpg), str(raw))
        out = tmp_path / "out"
        actions = plan_pair_layout(pairs, str(out), layout="raw-with-jpg", action="copy")
        copied, completed = execute_pair_actions(actions, dry_run=False, move=False)
        assert copied == 4  # 2 pairs × (jpg + raw)
        assert (out / "RAW" / "DSC001.arw").exists()
        assert (out / "RAW" / "DSC001.jpg").exists()
        # 來源保留（copy 模式）
        assert (jpg / "DSC001.jpg").exists()

    def test_execute_failure_isolated(self, tmp_path, monkeypatch):
        jpg, raw = _setup(tmp_path)
        pairs, _, _ = pair_by_stem(str(jpg), str(raw))
        actions = plan_pair_layout(pairs, str(tmp_path / "out"), layout="raw-with-jpg", action="copy")

        import shutil

        real_copy = shutil.copy2
        calls = {"n": 0}

        def flaky_copy(src, dst, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("boom")
            return real_copy(src, dst, **kwargs)

        monkeypatch.setattr("core.pairing.shutil.copy2", flaky_copy)
        copied, completed = execute_pair_actions(actions, dry_run=False, move=False)
        assert copied == 3
        assert sum(1 for a in completed if a.action == "failed") == 1
