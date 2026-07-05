from __future__ import annotations

from core.photo_executor import execute_photo_actions
from core.photo_planner import plan_photo_actions

PRESET = {
    "RAW": {".arw", ".cr2", ".nef", ".raf", ".dng", ".rw2"},
    "JPG": {".jpg", ".jpeg", ".heic"},
    "VIDEO": {".mp4", ".mov", ".avi", ".mkv"},
    "OTHERS": set(),
}


def _plan(source, output, **kwargs):
    defaults = dict(
        source_folder=str(source),
        output_folder=str(output),
        recursive=True,
        preset=PRESET,
        layout="by-date-type",
        pair_key_mode="stem",
        enable_duplicates=True,
        dupe_strategy="latest",
        prefer_path=None,
        partial_size_mb=1,
        full_hash_algo="sha256",
    )
    defaults.update(kwargs)
    return plan_photo_actions(**defaults)


class TestPlanPhotoActions:
    def test_plan_does_not_touch_disk(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "DSC001.jpg").write_bytes(b"jpg-data-1")
        (src / "DSC001.arw").write_bytes(b"raw-data-1")
        out = tmp_path / "out"
        plan = _plan(src, out)
        assert len(plan.pairs) == 1
        assert not out.exists(), "規劃階段不應建立資料夾"

    def test_same_basename_distinct_destinations(self, tmp_path):
        """相機資料夾換頁造成的同名檔案不能互相覆蓋（覆蓋 bug 回歸測試）。"""
        src = tmp_path / "src"
        (src / "100MSDCF").mkdir(parents=True)
        (src / "101MSDCF").mkdir(parents=True)
        f1 = src / "100MSDCF" / "DSC001.jpg"
        f2 = src / "101MSDCF" / "DSC001.jpg"
        f1.write_bytes(b"photo-one")
        f2.write_bytes(b"photo-two!")
        import os

        # 同一天拍攝 → 同一個日期資料夾
        os.utime(f1, (1704067200, 1704067200))
        os.utime(f2, (1704070000, 1704070000))

        plan = _plan(src, tmp_path / "out")
        dests = [a.dest_path for a in plan.photo_actions]
        assert len(dests) == len(set(dests)), "同名檔案解析到相同目的地"

        # 執行後兩份內容都存在
        completed = execute_photo_actions(plan.photo_actions, dry_run=False, move=False)
        assert all(a.action == "copied" for a in completed)
        contents = {p.read_bytes() for p in (tmp_path / "out").rglob("DSC001*.jpg")}
        assert contents == {b"photo-one", b"photo-two!"}

    def test_duplicates_detected_and_planned(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.jpg").write_bytes(b"identical-photo")
        (src / "b.jpg").write_bytes(b"identical-photo")
        plan = _plan(src, tmp_path / "out")
        assert len(plan.duplicate_matches) == 1
        assert len(plan.photo_actions) == 1  # 只剩保留的那份

    def test_disable_duplicates(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.jpg").write_bytes(b"identical-photo")
        (src / "b.jpg").write_bytes(b"identical-photo")
        plan = _plan(src, tmp_path / "out", enable_duplicates=False)
        assert plan.duplicate_matches == []
        assert len(plan.photo_actions) == 2
