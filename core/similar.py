from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

ProgressCallback = Callable[[int, int], None]

SIMILAR_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".heic", ".heif"}


@dataclass(frozen=True)
class SimilarFile:
    path: str
    phash: str
    distance: int  # 與群組代表（第一張）的 Hamming distance


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class BKTree:
    """以 Hamming distance 為度量的 BK-tree，hash 以 int 表示。

    int XOR + bit_count 比 imagehash 的 numpy 陣列運算快兩個數量級，
    是 BK-tree 大量距離計算的關鍵。節點存 hash 與對應的 index 清單
    （相同 hash 收在同一節點），子節點以「與父節點的距離」為 key。
    範圍查詢依三角不等式只走訪距離落在 [d - max, d + max] 的子樹。
    """

    __slots__ = ("_root",)

    def __init__(self) -> None:
        # node: [hash, indices, children({distance: node})]
        self._root: list | None = None

    def add(self, item_hash: int, index: int) -> None:
        if self._root is None:
            self._root = [item_hash, [index], {}]
            return
        node = self._root
        while True:
            distance = _hamming(item_hash, node[0])
            if distance == 0:
                node[1].append(index)
                return
            child = node[2].get(distance)
            if child is None:
                node[2][distance] = [item_hash, [index], {}]
                return
            node = child

    def search(self, item_hash: int, max_distance: int) -> list[tuple[int, int]]:
        """回傳所有距離 <= max_distance 的 (index, distance)。"""
        if self._root is None:
            return []
        results: list[tuple[int, int]] = []
        stack = [self._root]
        while stack:
            node = stack.pop()
            distance = _hamming(item_hash, node[0])
            if distance <= max_distance:
                results.extend((idx, distance) for idx in node[1])
            low = distance - max_distance
            high = distance + max_distance
            for child_distance, child in node[2].items():
                if low <= child_distance <= high:
                    stack.append(child)
        return results


def _compute_phash(path: str, hash_size: int):
    from PIL import Image
    import imagehash

    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except Exception:
        pass

    try:
        with Image.open(path) as img:
            return imagehash.phash(img, hash_size=hash_size)
    except Exception:
        return None


def _hash_to_int(item_hash) -> int:
    # ImageHash 的 str 是十六進位；空 hash 視為 0
    text = str(item_hash)
    return int(text, 16) if text else 0


def group_hashes(
    hashes: list[tuple[str, object]],
    max_distance: int,
) -> list[list[SimilarFile]]:
    """把 (path, ImageHash) 清單依 Hamming distance 門檻分群（BK-tree + union-find）。

    兩個削減走訪量的手法：相同 hash 先合併（每個唯一 hash 只查一次）、
    邊插入邊查詢（只跟已插入的唯一 hash 比，總走訪量減半）。
    """
    int_hashes = [_hash_to_int(h) for _, h in hashes]

    parent = list(range(len(hashes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    # 相同 hash 合併：代表 index → 其餘直接 union
    rep_of_hash: dict[int, int] = {}
    unique: list[tuple[int, int]] = []  # (hash, 代表 index)
    for i, item_hash in enumerate(int_hashes):
        rep = rep_of_hash.get(item_hash)
        if rep is None:
            rep_of_hash[item_hash] = i
            unique.append((item_hash, i))
        else:
            union(rep, i)

    # 邊插入邊查詢：每個唯一 hash 只跟先前插入的比
    tree = BKTree()
    for item_hash, rep in unique:
        for other_rep, _ in tree.search(item_hash, max_distance):
            union(other_rep, rep)
        tree.add(item_hash, rep)

    clusters: dict[int, list[int]] = {}
    for i in range(len(hashes)):
        clusters.setdefault(find(i), []).append(i)

    groups: list[list[SimilarFile]] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda idx: hashes[idx][0])
        rep_hash = int_hashes[members[0]]
        group = [
            SimilarFile(
                path=hashes[idx][0],
                phash=str(hashes[idx][1]),
                distance=_hamming(rep_hash, int_hashes[idx]),
            )
            for idx in members
        ]
        groups.append(group)

    groups.sort(key=lambda g: g[0].path)
    return groups


def find_similar_images(
    paths: list[str],
    max_distance: int = 5,
    hash_size: int = 8,
    progress: ProgressCallback | None = None,
) -> list[list[SimilarFile]]:
    """用 perceptual hash 找內容近似的照片（不同解析度、輕度編輯）。

    max_distance 為 Hamming distance 門檻：0 = 幾乎相同，5 = 預設，
    越大越寬鬆（誤判也越多）。鄰近搜尋走 BK-tree（int hash + bit_count），
    數萬張的分群在數十秒內；整體瓶頸在讀圖算 hash（有 progress 回報）。
    """
    image_paths = [
        p for p in paths if os.path.splitext(p)[1].lower() in SIMILAR_IMAGE_EXTS
    ]
    total = len(image_paths)

    hashes: list[tuple[str, object]] = []
    for index, path in enumerate(image_paths, start=1):
        if progress:
            progress(index, total)
        h = _compute_phash(path, hash_size)
        if h is not None:
            hashes.append((path, h))

    return group_hashes(hashes, max_distance)
