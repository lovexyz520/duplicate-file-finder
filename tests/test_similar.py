from __future__ import annotations

import random

from PIL import Image

from core.similar import find_similar_images


def _make_blocks(path: str, size: tuple[int, int], seed: int = 42) -> None:
    """有結構的測試圖（16x16 隨機色塊放大），縮放後 phash 仍相近。"""
    random.seed(seed)
    base = Image.new("RGB", (16, 16))
    px = base.load()
    for x in range(16):
        for y in range(16):
            px[x, y] = (
                random.randrange(256),
                random.randrange(256),
                random.randrange(256),
            )
    base.resize(size, Image.NEAREST).save(path)


def test_finds_resized_versions(tmp_path):
    """同一張圖的不同解析度應被分到同一組。"""
    big = tmp_path / "big.jpg"
    small = tmp_path / "small.jpg"
    other = tmp_path / "other.jpg"
    _make_blocks(str(big), (256, 256), seed=42)
    _make_blocks(str(small), (64, 64), seed=42)
    _make_blocks(str(other), (128, 128), seed=999)  # 內容完全不同

    groups = find_similar_images([str(big), str(small), str(other)], max_distance=5)
    assert len(groups) == 1
    paths = {item.path for item in groups[0]}
    assert paths == {str(big), str(small)}


def test_no_similar_images(tmp_path):
    a = tmp_path / "a.jpg"
    _make_blocks(str(a), (64, 64))
    groups = find_similar_images([str(a)], max_distance=5)
    assert groups == []


def test_non_image_files_ignored(tmp_path):
    txt = tmp_path / "note.txt"
    txt.write_text("not an image")
    groups = find_similar_images([str(txt)], max_distance=5)
    assert groups == []


def test_progress_callback(tmp_path):
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    _make_blocks(str(a), (64, 64), seed=1)
    _make_blocks(str(b), (64, 64), seed=2)
    calls = []
    find_similar_images(
        [str(a), str(b)], max_distance=5, progress=lambda d, t: calls.append((d, t))
    )
    assert calls[-1] == (2, 2)
