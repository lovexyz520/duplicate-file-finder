"""
Duplicate File Finder - 重複檔案搜尋工具

比對兩個資料夾，找出並移動重複的檔案。

運作流程：
1. 掃描兩個資料夾中的檔案
2. 先比對檔案大小，大小不同則跳過（效能優化）
3. 對相同大小的檔案計算 xxhash（比 MD5 快 5-10 倍）
4. hash 相同時進行二進位比對確認
5. 將 folder2 中的重複檔案移動到輸出資料夾

使用方式：
    uv run find_duplicates.py [folder1] [folder2] [-o OUTPUT] [-r] [--dry-run]
"""

import argparse
import filecmp
import os
import shutil

import xxhash

# 預設資料夾路徑
DEFAULT_FOLDER1 = 'folder1'
DEFAULT_FOLDER2 = 'folder2'
DEFAULT_OUTPUT = 'output_folder'

# 舊路徑參考：
# folder1 = 'E://待整理 poto//mobile phone//手機備份//photo'
# folder2 = 'E://待整理 poto//mobile phone//手機備份//photo'
# output_folder = 'E://待整理 poto//mobile phone//手機備份//output_folder'


def get_hash(filename):
    """計算檔案的 xxhash 值（比 MD5 快 5-10 倍）

    Returns:
        str: 檔案的 hash 值，或 None 如果讀取失敗
    """
    try:
        hasher = xxhash.xxh64()
        with open(filename, 'rb') as f:
            while True:
                data = f.read(65536)  # 64KB chunks for better performance
                if not data:
                    break
                hasher.update(data)
        return hasher.hexdigest()
    except PermissionError:
        print(f"\n警告: 無法讀取檔案（權限不足）- {filename}")
        return None
    except OSError as e:
        print(f"\n警告: 無法讀取檔案（{e.strerror}）- {filename}")
        return None


def check_overlapping_folders(folder1, folder2):
    """檢查兩個資料夾是否有重疊

    Returns:
        str: 重疊類型 ('same', 'folder1_contains_folder2', 'folder2_contains_folder1', None)
    """
    path1 = os.path.abspath(folder1)
    path2 = os.path.abspath(folder2)

    if path1 == path2:
        return 'same'

    # 確保路徑結尾有分隔符，避免誤判（如 /foo 和 /foobar）
    path1_with_sep = path1 + os.sep
    path2_with_sep = path2 + os.sep

    if path2.startswith(path1_with_sep):
        return 'folder1_contains_folder2'
    if path1.startswith(path2_with_sep):
        return 'folder2_contains_folder1'

    return None


def get_files_with_size(folder, recursive=False):
    """取得資料夾下的所有檔案及其大小（排除子目錄）"""
    files = []
    if recursive:
        for root, _, filenames in os.walk(folder):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                files.append((filepath, os.path.getsize(filepath)))
    else:
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                files.append((filepath, os.path.getsize(filepath)))
    return files


def find_duplicates(folder1, folder2, output_folder, recursive=False, dry_run=False):
    """找出並移動重複檔案"""
    # 確保輸出資料夾存在
    os.makedirs(output_folder, exist_ok=True)

    # 取得兩個資料夾下的所有檔案及大小
    files1 = get_files_with_size(folder1, recursive)
    files2 = get_files_with_size(folder2, recursive)

    print(f"資料夾 1: {len(files1)} 個檔案")
    print(f"資料夾 2: {len(files2)} 個檔案")

    # 建立 folder1 的大小索引 {size: [filepath, ...]}
    size_index1 = {}
    for filepath, size in files1:
        if size not in size_index1:
            size_index1[size] = []
        size_index1[size].append(filepath)

    # 找出 folder2 中與 folder1 有相同大小的檔案
    candidates = []
    for filepath, size in files2:
        if size in size_index1:
            candidates.append((filepath, size, size_index1[size]))

    print(f"相同大小的候選檔案: {len(candidates)} 個")

    if not candidates:
        print("沒有找到重複檔案")
        return

    print("正在計算 hash...")

    # 計算 folder1 候選檔案的 hash（只計算有相同大小的）
    hash_cache1 = {}
    sizes_needed = set(c[1] for c in candidates)
    files1_to_hash = [(f, s) for f, s in files1 if s in sizes_needed]

    for i, (filepath, _) in enumerate(files1_to_hash, 1):
        print(f"\r資料夾 1: {i}/{len(files1_to_hash)}", end="", flush=True)
        file_hash = get_hash(filepath)
        if file_hash is not None:
            hash_cache1[filepath] = file_hash
    print()

    # 處理候選檔案
    moved_count = 0
    for i, (file2, size, matching_files1) in enumerate(candidates, 1):
        print(f"\r資料夾 2: {i}/{len(candidates)}", end="", flush=True)

        # 跳過同一個檔案
        file2_abs = os.path.abspath(file2)

        hash2 = get_hash(file2)
        if hash2 is None:
            continue  # 無法讀取檔案，跳過

        for file1 in matching_files1:
            if os.path.abspath(file1) == file2_abs:
                continue

            hash1 = hash_cache1.get(file1)
            if hash1 is None or hash1 != hash2:
                continue

            # hash 相同，進行二進位比對確認
            if filecmp.cmp(file1, file2, shallow=False):
                dest = os.path.join(output_folder, os.path.basename(file2))

                # 處理檔名衝突
                if os.path.exists(dest):
                    base, ext = os.path.splitext(os.path.basename(file2))
                    counter = 1
                    while os.path.exists(dest):
                        dest = os.path.join(output_folder, f"{base}_{counter}{ext}")
                        counter += 1

                if dry_run:
                    print(f"\n[預覽] 將移動: {file2} -> {dest}")
                else:
                    shutil.move(file2, dest)
                    print(f"\n已移動: {file2} -> {dest}")
                moved_count += 1
                break  # 已找到重複，跳出內層迴圈

    print(f"\n\n共處理 {len(candidates)} 個候選檔案，移動 {moved_count} 個重複檔案")


def main():
    parser = argparse.ArgumentParser(description="比對兩個資料夾，找出並移動重複的檔案")
    parser.add_argument("folder1", nargs="?", default=DEFAULT_FOLDER1, help="第一個資料夾路徑")
    parser.add_argument("folder2", nargs="?", default=DEFAULT_FOLDER2, help="第二個資料夾路徑")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="輸出資料夾路徑")
    parser.add_argument("-r", "--recursive", action="store_true", help="遞迴掃描子資料夾")
    parser.add_argument("--dry-run", action="store_true", help="預覽模式，不實際移動檔案")

    args = parser.parse_args()

    # 檢查資料夾是否存在
    if not os.path.isdir(args.folder1):
        print(f"錯誤: 資料夾不存在 - {args.folder1}")
        return
    if not os.path.isdir(args.folder2):
        print(f"錯誤: 資料夾不存在 - {args.folder2}")
        return

    # 檢查資料夾是否重疊
    overlap = check_overlapping_folders(args.folder1, args.folder2)
    if overlap == 'same':
        print("錯誤: folder1 和 folder2 是同一個資料夾")
        return
    if overlap == 'folder1_contains_folder2':
        print("警告: folder2 是 folder1 的子資料夾，可能導致非預期的結果")
        response = input("是否繼續？(y/N): ").strip().lower()
        if response != 'y':
            print("已取消")
            return
    if overlap == 'folder2_contains_folder1':
        print("警告: folder1 是 folder2 的子資料夾，可能導致非預期的結果")
        response = input("是否繼續？(y/N): ").strip().lower()
        if response != 'y':
            print("已取消")
            return

    find_duplicates(args.folder1, args.folder2, args.output, args.recursive, args.dry_run)


if __name__ == "__main__":
    main()
