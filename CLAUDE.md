# 檔案管理工具箱 v3.1.0

## 專案概述

一套完整的檔案整理解決方案，包含四大功能模組：

| 模組 | CLI | Streamlit UI | 說明 |
|------|-----|--------------|------|
| 重複檔案偵測 | `find_duplicates.py` | ✅ | 比對兩個資料夾，三層 hash 比對 |
| 工作檔案整理 | `organize_files.py` | ✅ | 依副檔名分類 + 時間分層 |
| RAW/JPG 配對 | `pair_raw.py` | ✅ | 攝影檔案配對與整理 |
| 攝影素材整理 | `photo_organize.py` | ✅ | 日期分類 + 成對整理 + 重複隔離 |

## 技術架構

- **語言**：Python 3.10+
- **套件管理**：UV
- **主要依賴**：
  - `xxhash`：快速 partial hash
  - `hashlib`：SHA256 完整 hash
  - `streamlit`：圖形介面
  - `exifread`：EXIF metadata
  - `hachoir`：影片 metadata

## 專案結構

```
duplicate-file-finder/
├── core/                     # 核心模組
│   ├── actions.py            # 移動重複檔案 + 衝突命名
│   ├── dupe.py               # 三層比對邏輯
│   ├── hashers.py            # partial hash / full hash
│   ├── naming.py             # 檔名清理 + 命名衝突
│   ├── organizer.py          # 工作檔案整理
│   ├── pairing.py            # RAW/JPG 配對
│   ├── media_scanner.py      # 攝影素材掃描
│   ├── media_types.py        # 媒體檔案型別
│   ├── metadata.py           # EXIF / 影片 metadata
│   ├── photo_pairing.py      # 攝影素材成對
│   ├── photo_planner.py      # 攝影素材整理計畫
│   ├── photo_executor.py     # 攝影素材執行 + log
│   ├── report.py             # CSV 報表輸出
│   ├── scanner.py            # 檔案掃描
│   ├── types.py              # 資料結構
│   └── __init__.py           # 模組匯出
├── find_duplicates.py        # 重複檔案 CLI
├── organize_files.py         # 工作檔案整理 CLI
├── pair_raw.py               # RAW/JPG 配對 CLI
├── photo_organize.py         # 攝影素材整理 CLI
├── rules_presets.py          # 分類規則 preset
├── streamlit_app.py          # Streamlit UI（v3.1.0）
├── pyproject.toml
├── uv.lock
├── README.md
└── CLAUDE.md
```

## 核心演算法

### 重複檔案比對（三層 hash）

```
檔案大小過濾 → partial hash（xxhash 前/後 1MB）→ full hash（SHA256/xxhash64）
```

### 命名衝突處理

```python
# naming.py
原始檔名 → 清理（移除副本後綴、空白正規化）→ 衝突時補碼（_001, _002...）
```

### 配對邏輯

```python
# pairing.py / photo_pairing.py
key_mode:
  - stem: 檔名（不含副檔名）
  - stem+parent: 檔名 + 父資料夾名
  - exif: EXIF 拍攝時間
```

## 執行方式

```bash
# CLI
uv run find_duplicates.py --dry-run
uv run organize_files.py "C:\Downloads" -o "C:\Organized" --dry-run
uv run pair_raw.py "C:\JPG" "C:\RAW" -o "C:\Pairs" --dry-run
uv run photo_organize.py "C:\Photos" -o "C:\Output" --dry-run

# Streamlit UI
uv run streamlit run streamlit_app.py
```

## 主要 API

### core/__init__.py 匯出

```python
# 掃描
scan_folder(folder, recursive) -> list[FileInfo]
scan_media_folder(...) -> list[MediaFileInfo]

# 重複檔案
find_duplicates_between(files1, files2, partial_bytes, full_hash_algo) -> list[DuplicateMatch]
group_duplicates(files, partial_bytes, full_hash_algo) -> list[list[FileInfo]]
move_duplicates(matches, output_folder, ...) -> tuple[int, list[DuplicateAction]]

# 整理
organize(...) -> tuple[int, list[DuplicateMatch], list[DuplicateAction], list[OrganizeAction]]

# RAW/JPG 配對
pair_by_stem(...) -> tuple[list[PairRecord], list[str], list[str]]
plan_pair_layout(pairs, output_folder, layout, ...) -> list[PairAction]
execute_pair_actions(actions, dry_run, move) -> tuple[int, list[PairAction]]

# 攝影素材
plan_photo_actions(...) -> PhotoPlan
execute_photo_actions(actions, dry_run, move) -> list[PhotoAction]
execute_duplicate_actions(actions, dry_run) -> list[DuplicateAction]

# 報表
write_duplicates_report(matches, path, actions)
write_organize_report(actions, path)
write_pairs_report(pairs, orphan_jpgs, orphan_raws, pairs_path, orphans_path)
```

## Streamlit UI 架構（v3.1.0）

### 功能模式

- 🔍 重複檔案偵測 → `duplicate_finder_ui()`
- 📁 工作檔案整理 → `file_organizer_ui()`
- 📷 RAW/JPG 配對 → `raw_jpg_pairing_ui()`
- 🎞️ 攝影素材整理 → `photo_organizer_ui()`

### Session State 管理

```python
st.session_state.results_*      # 各模式預覽結果
st.session_state.history        # 操作歷史（最多 20 筆）
st.session_state.settings       # 使用者設定（記憶體）
.streamlit_settings.json        # 使用者設定（持久化）
```

### UI 共用元件

```python
_path_input()           # 路徑輸入 + 📁 資料夾選擇器
_select_with_mapping()  # 下拉選單 + 值對應
_dupe_settings_ui()     # 重複檔案偵測設定區塊
_cleaning_settings_ui() # 檔名清理設定區塊
_show_progress()        # 進度條顯示
_add_history()          # 新增操作歷史
_clear_results_button() # 清除結果按鈕
```

### UI 功能特色

- 進度條顯示
- 預估檔案數量
- 一鍵預覽 / 清除結果
- 成功動畫（balloons + toast）
- 操作歷史（側邊欄）
- 設定自動儲存
- 圖片預覽（攝影模式）

## 分類規則 Preset

### WORK_PRESET（工作檔案）

```python
{
    "Docs": {".doc", ".docx", ".txt", ".md"},
    "PDF": {".pdf"},
    "Sheets": {".xls", ".xlsx", ".csv"},
    "Slides": {".ppt", ".pptx"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".json", ".ts", ".html", ".css", ".yml", ".yaml"},
    "Others": set(),
}
```

### PHOTO_PRESET（攝影素材）

```python
{
    "RAW": {".arw", ".cr2", ".nef", ".raf", ".dng", ".rw2"},
    "JPG": {".jpg", ".jpeg", ".heic"},
    "VIDEO": {".mp4", ".mov", ".avi", ".mkv"},
    "OTHERS": set(),
}
```

## 注意事項

- 請先用 `--dry-run` 或「一鍵預覽」預覽
- Windows CMD 可能顯示中文亂碼（不影響功能）
- Streamlit UI 設定會自動儲存至 `.streamlit_settings.json`
- 測試資料夾（folder1, folder2, output_folder）已加入 .gitignore
