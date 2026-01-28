from __future__ import annotations

import hashlib
import os

import xxhash


def partial_hash(path: str, chunk_bytes: int) -> str | None:
    try:
        size = os.path.getsize(path)
        hasher = xxhash.xxh64()
        with open(path, "rb") as f:
            if size <= chunk_bytes * 2:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    hasher.update(data)
            else:
                head = f.read(chunk_bytes)
                hasher.update(head)
                f.seek(-chunk_bytes, os.SEEK_END)
                tail = f.read(chunk_bytes)
                hasher.update(tail)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None


def full_hash(path: str, algo: str = "sha256") -> str | None:
    try:
        algo_lower = algo.lower()
        if algo_lower == "sha256":
            hasher = hashlib.sha256()
        elif algo_lower == "xxhash64":
            hasher = xxhash.xxh64()
        else:
            raise ValueError(f"Unsupported full hash algorithm: {algo}")
        with open(path, "rb") as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                hasher.update(data)
        return hasher.hexdigest()
    except (OSError, PermissionError):
        return None
