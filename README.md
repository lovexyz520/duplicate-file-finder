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

# 指定報表輸出路徑（預設: output_folder/duplicates_report.csv）
uv run find_duplicates.py --report "C:\重複檔案\duplicates_report.csv"

# 調整 partial hash 大小與完整 hash 演算法
uv run find_duplicates.py --partial-size-mb 2 --full-hash xxhash64

# 保留策略與移動範圍
uv run find_duplicates.py --keep-strategy latest
uv run find_duplicates.py --keep-strategy earliest
uv run find_duplicates.py --keep-strategy prefer-path --prefer-path "C:\主資料庫"
uv run find_duplicates.py --keep-strategy latest --move-scope both
```

## 參數說明

| 參數 | 說明 |
|------|------|
| `folder1` | 第一個資料夾路徑（預設：`folder1`） |
| `folder2` | 第二個資料夾路徑（預設：`folder2`） |
| `-o`, `--output` | 輸出資料夾路徑（預設：`output_folder`） |
| `-r`, `--recursive` | 遞迴掃描子資料夾 |
| `--dry-run` | 預覽模式，只顯示會移動的檔案，不實際執行 |
| `--report` | 報表輸出路徑（預設：`output_folder/duplicates_report.csv`） |
| `--partial-size-mb` | partial hash 讀取前/後大小（MB，預設：1） |
| `--full-hash` | 完整 hash 演算法（`sha256` 或 `xxhash64`） |
| `--keep-strategy` | 保留策略（`folder1`/`folder2`/`latest`/`earliest`/`prefer-path`） |
| `--prefer-path` | 保留策略為 `prefer-path` 時指定路徑前綴 |
| `--move-scope` | 移動範圍（`folder2`/`both`；預設只移動 folder2） |

## 運作原理

1. 掃描兩個資料夾中的檔案
2. 先比對檔案大小，大小不同則跳過
3. 對相同大小的檔案計算 partial hash（前/後 1MB 的 xxhash）
4. partial hash 相同時進行完整 SHA256
5. 將 folder2 中的重複檔案移動到輸出資料夾

## 報表說明

預設會輸出 `output_folder/duplicates_report.csv`，也可用 `--report` 指定路徑。

### 欄位

| 欄位 | 說明 |
|------|------|
| `duplicate_path` | 被判定為重複的檔案路徑 |
| `original_path` | 保留參考的對應檔案路徑 |
| `size` | 檔案大小（bytes） |
| `mtime_duplicate` | 重複檔案的修改時間（timestamp） |
| `mtime_original` | 原始檔案的修改時間（timestamp） |
| `ctime_duplicate` | 重複檔案的建立時間（timestamp） |
| `ctime_original` | 原始檔案的建立時間（timestamp） |
| `partial_hash` | partial hash 值（前/後 1MB 的 xxhash） |
| `full_hash` | 完整 hash 值（SHA256 或 xxhash64） |
| `action` | 執行動作（`preview`/`moved`/`kept_by_strategy`） |
| `strategy` | 使用的保留策略 |
| `keep_path` | 被保留的檔案路徑 |
| `move_path` | 被移動的檔案路徑 |

### 範例

```csv
duplicate_path,original_path,size,mtime_duplicate,mtime_original,ctime_duplicate,ctime_original,partial_hash,full_hash,action,strategy,keep_path,move_path
"C:\\B\\dup1.jpg","C:\\A\\dup1.jpg",1056234,1706371200,1706284800,1706371200,1706284800,ab12cd34,9f8e7d6c...,moved,folder1,"C:\\A\\dup1.jpg","C:\\Duplicates\\dup1.jpg"
```
