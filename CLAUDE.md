# Duplicate File Finder

## 專案概述

這是一個用於比對兩個資料夾並找出重複檔案的 Python 工具。重複的檔案會從 folder2 移動到指定的輸出資料夾。

## 技術架構

- **語言**: Python 3.10+
- **套件管理**: UV
- **主要依賴**: xxhash（高效能 hash 演算法）

## 檔案結構

```
duplicate-file-finder/
├── find_duplicates.py    # 主程式
├── pyproject.toml        # UV 專案設定
├── uv.lock               # 依賴鎖定檔
├── requirements.txt      # pip 依賴檔
├── README.md             # 使用說明
├── CLAUDE.md             # 開發指南（本檔案）
├── folder1/              # 測試用資料夾（已 gitignore）
├── folder2/              # 測試用資料夾（已 gitignore）
└── output_folder/        # 輸出資料夾（已 gitignore）
```

## 核心演算法

1. **檔案大小過濾**: 先比對檔案大小，只有大小相同的檔案才進入下一步
2. **xxhash 計算**: 使用 xxhash64 計算 hash，比 MD5 快 5-10 倍
3. **二進位比對**: hash 相同時用 `filecmp.cmp()` 做最終確認
4. **檔名衝突處理**: 輸出資料夾有同名檔案時自動加上 `_1`, `_2` 後綴

## 開發指南

### 執行程式

```bash
# 使用 UV
uv run find_duplicates.py --dry-run

# 使用 pip
pip install -r requirements.txt
python find_duplicates.py --dry-run
```

### 命令列參數

| 參數 | 說明 |
|------|------|
| `folder1` | 第一個資料夾（預設: `folder1`） |
| `folder2` | 第二個資料夾（預設: `folder2`） |
| `-o`, `--output` | 輸出資料夾（預設: `output_folder`） |
| `-r`, `--recursive` | 遞迴掃描子資料夾 |
| `--dry-run` | 預覽模式，不實際移動檔案 |

### 主要函數

- `get_hash(filename)`: 計算檔案的 xxhash64 值（含錯誤處理）
- `check_overlapping_folders(folder1, folder2)`: 檢查兩個資料夾是否重疊
- `get_files_with_size(folder, recursive)`: 取得資料夾內所有檔案及其大小
- `find_duplicates(...)`: 主要邏輯，找出並移動重複檔案

## 注意事項

- Windows CMD 可能會有中文顯示亂碼問題，不影響功能
- 測試資料夾 (`folder1/`, `folder2/`, `output_folder/`) 已加入 `.gitignore`
- 程式會移動（而非複製）重複檔案，請先用 `--dry-run` 預覽
