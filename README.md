# Duplicate File Finder

比對兩個資料夾，找出並移動重複的檔案。

## 安裝

```bash
uv sync
```

## 使用方式

```bash
# 使用預設資料夾 (folder1, folder2 -> output_folder)
uv run find_duplicates.py

# 指定資料夾
uv run find_duplicates.py "C:\照片A" "C:\照片B" -o "C:\重複檔案"

# 遞迴掃描子資料夾
uv run find_duplicates.py -r

# 預覽模式（不實際移動檔案）
uv run find_duplicates.py --dry-run
```

## 參數說明

| 參數 | 說明 |
|------|------|
| `folder1` | 第一個資料夾路徑（預設：`folder1`） |
| `folder2` | 第二個資料夾路徑（預設：`folder2`） |
| `-o`, `--output` | 輸出資料夾路徑（預設：`output_folder`） |
| `-r`, `--recursive` | 遞迴掃描子資料夾 |
| `--dry-run` | 預覽模式，只顯示會移動的檔案，不實際執行 |

## 運作原理

1. 掃描兩個資料夾中的檔案
2. 先比對檔案大小，大小不同則跳過
3. 對相同大小的檔案計算 hash 值（使用 xxhash，比 MD5 快 5-10 倍）
4. hash 相同時進行二進位比對確認
5. 將 folder2 中的重複檔案移動到輸出資料夾
