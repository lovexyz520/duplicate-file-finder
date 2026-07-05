from __future__ import annotations

import random

import imagehash
from PIL import Image

from core.similar import BKTree, find_similar_images, group_hashes


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


def _random_ints(count: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    return [rng.getrandbits(64) for _ in range(count)]


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class TestBKTree:
    def test_search_matches_brute_force(self):
        """BK-tree 範圍查詢結果必須與暴力法完全一致。"""
        hashes = _random_ints(200, seed=7)
        tree = BKTree()
        for i, h in enumerate(hashes):
            tree.add(h, i)

        for max_distance in (0, 3, 8, 20):
            for i in (0, 57, 123, 199):
                expected = {
                    (j, _hamming(hashes[i], hj))
                    for j, hj in enumerate(hashes)
                    if _hamming(hashes[i], hj) <= max_distance
                }
                assert set(tree.search(hashes[i], max_distance)) == expected

    def test_duplicate_hashes_share_node(self):
        h = _random_ints(1, seed=1)[0]
        tree = BKTree()
        tree.add(h, 0)
        tree.add(h, 1)
        assert sorted(tree.search(h, 0)) == [(0, 0), (1, 0)]

    def test_empty_tree(self):
        tree = BKTree()
        assert tree.search(_random_ints(1, seed=2)[0], 5) == []


def test_group_hashes_matches_brute_force_grouping():
    """BK-tree 分群結果必須與 O(n²) 暴力 union-find 一致（含 ImageHash 轉換）。"""
    rng = random.Random(42)
    hashes = [
        imagehash.hex_to_hash(f"{rng.getrandbits(64):016x}") for _ in range(150)
    ]
    items = [(f"img_{i:03d}.jpg", h) for i, h in enumerate(hashes)]
    max_distance = 12

    # 暴力法分群
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if hashes[i] - hashes[j] <= max_distance:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

    expected_clusters = {}
    for i in range(len(items)):
        expected_clusters.setdefault(find(i), set()).add(items[i][0])
    expected_groups = sorted(
        frozenset(g) for g in expected_clusters.values() if len(g) > 1
    )

    actual = group_hashes(items, max_distance)
    actual_groups = sorted(frozenset(item.path for item in g) for g in actual)

    assert actual_groups == expected_groups


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
