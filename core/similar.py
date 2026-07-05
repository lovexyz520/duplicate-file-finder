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


def find_similar_images(
    paths: list[str],
    max_distance: int = 5,
    hash_size: int = 8,
    progress: ProgressCallback | None = None,
) -> list[list[SimilarFile]]:
    """用 perceptual hash 找內容近似的照片（不同解析度、輕度編輯）。

    max_distance 為 Hamming distance 門檻：0 = 幾乎相同，5 = 預設，
    越大越寬鬆（誤判也越多）。O(n²) 比對，適合數千張以內的資料集。
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

    # union-find 分群
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

    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            if (hashes[i][1] - hashes[j][1]) <= max_distance:  # type: ignore[operator]
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(len(hashes)):
        clusters.setdefault(find(i), []).append(i)

    groups: list[list[SimilarFile]] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda idx: hashes[idx][0])
        rep_hash = hashes[members[0]][1]
        group = [
            SimilarFile(
                path=hashes[idx][0],
                phash=str(hashes[idx][1]),
                distance=int(rep_hash - hashes[idx][1]),  # type: ignore[operator]
            )
            for idx in members
        ]
        groups.append(group)

    groups.sort(key=lambda g: g[0].path)
    return groups
