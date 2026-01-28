# Duplicate File Finder

## 專案概述

這是一個用於比對兩個資料夾並找出重複檔案的 Python 工具。重複的檔案會從 folder2 移動到指定的輸出資料夾。

## 技術架構

- **語言**: Python 3.10+
- **套件管理**: UV
- **主要依賴**: xxhash（partial hash / full hash 選項）+ hashlib（SHA256）

## 檔案結構

```
duplicate-file-finder/
├── core/                # 核心模組
│   ├── actions.py       # 移動重複檔案 + 衝突命名處理
│   ├── dupe.py          # 三層比對邏輯
│   ├── hashers.py       # partial hash / full hash
│   ├── naming.py        # 檔名清理與命名衝突處理
│   ├── report.py        # CSV 報表輸出
│   ├── scanner.py       # 檔案掃描/metadata
│   └── types.py         # 資料結構
├── find_duplicates.py    # 主程式
├── organize_files.py     # 工作檔案整理助手（CLI）
├── rules_presets.py      # 分類規則 preset
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
2. **partial hash**: 前/後 1MB 用 xxhash64 計算
3. **完整 hash**: partial hash 相同才計算 SHA256
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
| `--report` | 報表輸出路徑（預設: `output_folder/duplicates_report.csv`） |
| `--partial-size-mb` | partial hash 讀取前/後大小（MB，預設: 1） |
| `--full-hash` | 完整 hash 演算法（`sha256` 或 `xxhash64`） |
| `--keep-strategy` | 保留策略（`folder1`/`folder2`/`latest`/`earliest`/`prefer-path`） |
| `--prefer-path` | 保留策略為 `prefer-path` 時指定路徑前綴 |
| `--move-scope` | 移動範圍（`folder2`/`both`；預設只移動 folder2） |
| `--clean-names` | 啟用檔名清理（移除(1)/(2)、空白正規化、移除特殊字元、衝突補 _001） |
| `--clean-copy-suffix` | 移除檔名結尾的 (1)/(2) 等副本後綴 |
| `--clean-normalize-space` | 空白正規化（多空白合併為一個） |
| `--clean-remove-special` | 移除檔名中的特殊字元 |
| `--clean-conflict-width` | 命名衝突自動補碼位數（預設: clean-names=3，其餘=1） |

### 主要函數

- `scan_folder(folder, recursive)`: 掃描資料夾並回傳檔案 metadata
- `find_duplicates_between(files1, files2, partial_bytes)`: 三層比對找出重複
- `move_duplicates(matches, output_folder, dry_run)`: 移動重複檔案
- `write_duplicates_report(matches, report_path)`: 產出 CSV 報表
  - 報表包含動作與命名衝突欄位（action/strategy/keep/move/desired_move_path/name_conflict）

## 注意事項

- Windows CMD 可能會有中文顯示亂碼問題，不影響功能
- 測試資料夾 (`folder1/`, `folder2/`, `output_folder/`) 已加入 `.gitignore`
- 程式會移動（而非複製）重複檔案，請先用 `--dry-run` 預覽
