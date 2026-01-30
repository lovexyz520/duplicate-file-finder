# Duplicate File Finder

## 專案概述

比對兩個資料夾找出重複檔案並移動，另提供工作檔案整理助手（CLI/Streamlit）。

## 技術架構

- 語言：Python 3.10+
- 套件管理：UV
- 主要依賴：xxhash（partial hash）+ hashlib（SHA256）+ streamlit（UI）

## 專案結構

```
duplicate-file-finder/
├── core/
│   ├── actions.py        # 移動重複檔案 + 衝突命名處理
│   ├── dupe.py           # 三層比對邏輯
│   ├── hashers.py        # partial hash / full hash
│   ├── naming.py         # 檔名清理與命名衝突處理
│   ├── organizer.py      # 工作檔案整理邏輯
│   ├── pairing.py        # RAW/JPG 配對工具
│   ├── report.py         # CSV 報表輸出
│   ├── scanner.py        # 檔案掃描/metadata
│   └── types.py          # 資料結構
├── find_duplicates.py     # 重複檔案 CLI
├── organize_files.py      # 工作檔案整理 CLI
├── pair_raw.py            # RAW/JPG 配對 CLI
├── rules_presets.py       # 分類規則 preset
├── streamlit_app.py       # Streamlit UI
├── pyproject.toml
├── uv.lock
├── requirements.txt
├── README.md
├── CLAUDE.md
├── folder1/               # 測試資料夾（gitignore）
├── folder2/               # 測試資料夾（gitignore）
└── output_folder/         # 輸出資料夾（gitignore）
```

## 核心演算法（重複檔案）

1. 檔案大小過濾
2. partial hash（前/後 1MB 的 xxhash）
3. 完整 hash（SHA256 或 xxhash64）
4. 命名衝突處理（補 _001）

## 執行方式

```bash
# CLI
uv run find_duplicates.py --dry-run
uv run organize_files.py "C:\Downloads" -o "C:\Organized" --dry-run

# Streamlit UI
uv run streamlit run streamlit_app.py

# RAW/JPG pairing CLI
uv run pair_raw.py "C:\SelectedJPG" "C:\AllRAW" -o "C:\RAW_Selected"
```

## 主要函數

- `scan_folder(folder, recursive)`
- `find_duplicates_between(files1, files2, partial_bytes, full_hash_algo)`
- `move_duplicates(matches, output_folder, dry_run, ...)`
- `group_duplicates(files, partial_bytes, full_hash_algo)`
- `organize(...)`（工作檔案整理）
- `write_duplicates_report(...)` / `write_organize_report(...)`
- `pair_by_stem(...)` / `plan_pair_layout(...)` / `execute_pair_actions(...)`

## 注意事項

- 請先用 `--dry-run` 預覽
- Windows CMD 可能顯示中文亂碼（不影響功能）
