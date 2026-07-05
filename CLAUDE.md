# 檔案管理工具箱 v3.2.0

## 專案概述

一套完整的檔案整理解決方案，所有執行都產生操作 log、可一鍵復原：

| 模組 | CLI | Streamlit UI | 說明 |
|------|-----|--------------|------|
| 重複檔案偵測 | `find_duplicates.py` | ✅ | 比對兩個資料夾，三層 hash 比對 |
| 單資料夾去重 | — | ✅ | 單一資料夾內重複分群，每組保留一份 |
| 相似照片偵測 | — | ✅ | perceptual hash 找近似照片 |
| 工作檔案整理 | `organize_files.py` | ✅ | 依副檔名分類 + 時間分層 |
| RAW/JPG 配對 | `pair_raw.py` | ✅ | 攝影檔案配對與整理 |
| 攝影素材整理 | `photo_organize.py` | ✅ | 日期分類 + 成對整理 + 重複隔離 |
| 復原操作 | `undo_actions.py` | ✅ | 從 actions log 反向還原 |

## 技術架構

- **語言**：Python 3.10+
- **套件管理**：UV
- **主要依賴**：
  - `xxhash`：快速 partial hash
  - `hashlib`：SHA256 完整 hash
  - `streamlit`：圖形介面
  - `exifread`：EXIF metadata（JPG/RAW）
  - `pillow` + `pillow-heif`：HEIC/HEIF EXIF、相似照片
  - `imagehash`：perceptual hash
  - `hachoir`：影片 metadata
  - `send2trash`：資源回收桶
  - `pytest`（dev）：測試

## 專案結構

```
duplicate-file-finder/
├── core/                     # 核心邏輯（純 Python，無 UI 依賴）
│   ├── actions.py            # move_duplicates：移動/回收桶 + 逐檔錯誤隔離
│   ├── dupe.py               # 三層比對、group_duplicates（回傳 hash）、pick_keep_for_group
│   ├── hashers.py            # partial hash / full hash
│   ├── naming.py             # 檔名清理 + DestinationResolver（防同批覆蓋）
│   ├── oplog.py              # 統一操作 log（JSONL）：make_record / write / read
│   ├── organizer.py          # 工作檔案整理（單一 pass，dry-run 零副作用）
│   ├── pairing.py            # RAW/JPG 配對 + plan/execute
│   ├── paths.py              # check_overlapping / path_is_within
│   ├── media_scanner.py      # 攝影素材掃描（EXIF/影片 metadata）
│   ├── media_types.py        # 媒體檔案型別
│   ├── metadata.py           # EXIF（exifread）/ HEIC（Pillow）/ 影片（hachoir）
│   ├── photo_pairing.py      # 攝影素材成對
│   ├── photo_planner.py      # 攝影素材整理計畫（純規劃）
│   ├── photo_executor.py     # 攝影素材執行 + oplog 轉換
│   ├── report.py             # CSV 報表（寫檔 + in-memory 字串供下載）
│   ├── scanner.py            # 檔案掃描 + 過濾（min_size/hidden/exclude_dirs）
│   ├── similar.py            # 相似照片偵測（imagehash phash + union-find）
│   ├── types.py              # 資料結構（action 均含 error 欄位）
│   ├── undo.py               # plan_undo / execute_undo（LIFO、模擬 fs 狀態）
│   └── __init__.py           # 模組匯出 + __version__
├── ui/                       # Streamlit UI（每模式一檔）
│   ├── common.py             # 設定持久化、歷史、ProgressBar、下載按鈕、過濾 UI
│   ├── dupe.py / single_dupe.py / similar.py
│   ├── organizer.py / pairing.py / photo.py / undo_ui.py
├── tests/                    # pytest（60+ 案例，含覆蓋 bug 回歸測試）
├── find_duplicates.py        # 重複檔案 CLI
├── organize_files.py         # 工作檔案整理 CLI
├── pair_raw.py               # RAW/JPG 配對 CLI
├── photo_organize.py         # 攝影素材整理 CLI
├── undo_actions.py           # 復原 CLI
├── rules_presets.py          # 分類規則 preset
├── streamlit_app.py          # UI 入口（薄殼，模式表驅動）
├── pyproject.toml            # version 與 core.__version__ 同步
└── README.md
```

## 核心設計原則（改動時必須遵守）

1. **預覽零副作用**：`dry_run=True` / 各 `plan_*` 函式不得觸碰磁碟（不 makedirs、不寫報表）。目錄由 executor 在執行時建立。
2. **目的地防碰撞**：解析目的地一律透過 `DestinationResolver`（同一批計畫共用一個 instance），它同時檢查磁碟與本批已配置路徑，防止同名檔互相覆蓋。
3. **逐檔錯誤隔離**：executor 對每個檔案 try/except，失敗記為 `action="failed"` + `error`，不中斷整批。
4. **操作 log**：所有實際執行都寫 `actions_log_*.jsonl`（`core/oplog.py` 統一格式：op/source/dest/status/kind），供 `core/undo.py` 還原。
5. **還原順序**：undo 按 LIFO 執行，存在性檢查在執行階段做（配合模擬 fs 狀態，支援鏈式移動還原）。

## 核心演算法

### 重複檔案比對（三層 hash）

```
檔案大小過濾 → partial hash（xxhash 前/後 1MB）→ full hash（SHA256/xxhash64）
```

`group_duplicates` 回傳 `list[list[GroupedFile]]`（含算好的 hash），呼叫端不得重算。

### 相似照片

`imagehash.phash` + Hamming distance 門檻 + union-find 分群。O(n²)，適合數千張以內。

### 配對邏輯

```python
# pairing.py / photo_pairing.py
key_mode:
  - stem: 檔名（不含副檔名）
  - stem+parent: 檔名 + 父資料夾名
  - exif: EXIF 拍攝時間（精度只到秒，連拍會撞 key → 可能錯配）
```

## 執行方式

```bash
# CLI（--dry-run 預覽；執行後印出 undo 指令）
uv run find_duplicates.py --dry-run
uv run organize_files.py "C:\Downloads" -o "C:\Organized" --dry-run
uv run pair_raw.py "C:\JPG" "C:\RAW" -o "C:\Pairs" --dry-run
uv run photo_organize.py "C:\Photos" -o "C:\Output" --dry-run
uv run undo_actions.py "<actions_log_*.jsonl>" --dry-run

# Streamlit UI
uv run streamlit run streamlit_app.py

# 測試
uv run pytest tests
```

## 主要 API（core/__init__.py 匯出）

```python
# 掃描（皆支援 min_size / include_hidden / exclude_dirs）
scan_folder(folder, recursive, ...) -> list[FileInfo]
scan_media_folder(..., progress=None) -> list[MediaFileInfo]
iter_files(folder, recursive, include_hidden, exclude_dirs)

# 重複檔案（progress=Callable[[int,int],None]）
find_duplicates_between(files1, files2, partial_bytes, full_hash_algo, progress) -> list[DuplicateMatch]
group_duplicates(files, partial_bytes, full_hash_algo, progress) -> list[list[GroupedFile]]
pick_keep_for_group(group, strategy, prefer_path) -> FileInfo
move_duplicates(matches, output_folder, ..., to_trash=False, progress=None) -> tuple[int, list[DuplicateAction]]

# 整理（progress=Callable[[stage,int,int],None]，stage: "hash"|"move"）
organize(..., min_size, include_hidden, exclude_dirs, write_reports, progress) -> tuple[...]

# RAW/JPG 配對
pair_by_stem(...) -> tuple[list[PairRecord], list[str], list[str]]
plan_pair_layout(pairs, output_folder, layout, ...) -> list[PairAction]   # 純規劃
execute_pair_actions(actions, dry_run, move, progress) -> tuple[int, list[PairAction]]

# 攝影素材（plan 純規劃；progress stage: "scan"|"hash"）
plan_photo_actions(...) -> PhotoPlan
execute_photo_actions(actions, dry_run, move, progress) -> list[PhotoAction]
execute_duplicate_actions(actions, dry_run, progress) -> list[DuplicateAction]

# 相似照片
find_similar_images(paths, max_distance=5, progress=None) -> list[list[SimilarFile]]

# 操作 log 與復原
make_record(op, source, dest, status, kind, **extra) -> dict
write_oplog(records, log_path) / read_oplog(log_path)
default_log_path(output_folder) -> str          # actions_log_YYYYMMDD_HHMMSS.jsonl
*_actions_to_records(...)                        # 各 action → oplog record
plan_undo(records) -> list[UndoAction]
execute_undo(actions, dry_run, progress) -> list[UndoAction]
undo_from_log(log_path, dry_run) -> list[UndoAction]

# 報表（寫檔版 + in-memory 字串版供 st.download_button）
write_duplicates_report / duplicates_report_csv
write_organize_report / organize_report_csv
write_pairs_report / pairs_report_csv / orphans_report_csv

# 路徑
check_overlapping(folder1, folder2) -> "same" | "folder1_contains_folder2" | ... | None
path_is_within(path, prefix) -> bool
```

## Streamlit UI 架構（v3.2.0）

- 入口 `streamlit_app.py`：側邊欄模式表 → 呼叫 `ui/<mode>.py` 的 `*_ui()`
- 共用元件在 `ui/common.py`：`path_input`、`ProgressBar`（多階段映射到單一進度條）、`download_csv_button`（UTF-8 BOM）、`filter_settings_ui`、`dupe_settings_ui`、`clean_settings_ui`、歷史（含 undo log 路徑）、`.streamlit_settings.json` 持久化
- UI 安全規則：
  - 重複偵測擋下 folder1 == folder2（會兩份都移走）；互為子資料夾需勾選確認
  - 預覽結果存在 session state；執行時**直接採用預覽清單**（所見即所得），無預覽才重新計算
  - 預覽不寫磁碟，報表用 download button；執行後才寫報表 + oplog + 顯示還原提示

## 分類規則 Preset（rules_presets.py）

- `WORK_PRESET`：Docs/PDF/Sheets/Slides/Images/Videos/Archives/Code/Others
- `PHOTO_PRESET`：RAW（.arw/.cr2/.nef/.raf/.dng/.rw2）/ JPG（.jpg/.jpeg/.heic）/ VIDEO / OTHERS

## 注意事項

- 請先用 `--dry-run` 或「一鍵預覽」預覽
- EXIF 配對精度只到秒，連拍素材建議用 stem 配對
- HEIC 的 EXIF 走 Pillow + pillow-heif（exifread 不支援 HEIC 容器）
- 影片拍攝時間轉為**本地時區** naive datetime（與檔案 mtime 一致）
- 資源回收桶（trashed）項目無法自動還原
- Windows CMD 可能顯示中文亂碼（不影響功能）
- 測試資料夾（folder1, folder2, output_folder）已加入 .gitignore
- 版本號：`pyproject.toml` 與 `core/__init__.py` 的 `__version__` 需同步更新
