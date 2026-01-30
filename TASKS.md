# Duplicate File Finder - Task Tracker

Last updated: 2026-01-28

## Implementation Spec (Requested)

### P0 - RAW/JPG 配對複製工具（核心 + CLI）
- [x] **Spec: core/pairing.py**
  - 功能：在 JPG 資料夾與 RAW 資料夾間以「檔名 stem」配對，支援大小寫不敏感。
  - RAW 副檔名：`.arw .cr2 .nef .raf .dng .rw2`（可擴充）。
  - Inputs:
    - `jpg_folder: str`
    - `raw_folder: str`
    - `recursive: bool`
    - `raw_exts: set[str]`
  - Output:
    - `pairs: list[tuple[jpg_path, raw_path]]`
    - `orphans_jpg: list[jpg_path]`
    - `orphans_raw: list[raw_path]`
- [x] **Spec: core/copy.py (or reuse actions.py with copy mode)**
  - `copy_pairs(pairs, output_folder, dry_run, clean_names, conflict_suffix_width)`
  - 命名衝突：沿用 `resolve_destination()`。
  - 回傳：`copied_count, operations`
- [x] **Spec: report/pairs**
  - `pairs.csv`: `jpg_path, raw_path`
  - `orphans.csv`: `path, type(jpg|raw)`
- [x] **CLI: pair_raw.py**
  - 用法：
    - `uv run pair_raw.py "<JPG_FOLDER>" "<RAW_FOLDER>" -o "<OUTPUT>" --dry-run`
  - 參數：
    - `-r/--recursive`
    - `--raw-exts ".ARW,.CR2,..."`（可選）
    - `--copy` / `--dry-run`
  - 結果：顯示配對數量、複製數量、孤兒數量，輸出報表。

### P1 - 攝影素材整理 MVP（Preset + Pipeline）
- [ ] **Spec: rules_presets.py**
  - 新增 `PHOTO_PRESET` 類別：
    - `RAW` / `JPG` / `VIDEO` / `OTHERS`
  - 支援 JPG/HEIC
- [ ] **Spec: planner.py**
  - 輸入資料夾掃描（遞迴），建立「日期 + 類型」目標路徑計畫。
  - 日期來源優先序：EXIF 拍攝時間 > 檔案 mtime。
  - 產出 `actions`（move/copy），供 executor 執行。
- [ ] **Spec: executor.py**
  - 執行 move/copy，輸出 `actions_log.jsonl`（可回復用）。
  - 產生 `duplicates_report.csv`（若啟用重複偵測）。
- [ ] **Spec: report**
  - `pairs.csv` / `orphans.csv` / `actions_log.jsonl`

### P2 - Streamlit UI 整合
- [ ] **UI: 新增模式「攝影素材整理」**
  - Step1: 選來源/目標
  - Step2: 模式（攝影）
  - Step3: 掃描 → 預覽表格 + 統計
  - Step4: 勾選確認 → 執行 Move/Copy
- [x] **UI: RAW/JPG 配對工具整合**
  - 可獨立頁籤或攝影模式內子功能。
  - 顯示配對數、孤兒數、複製清單。

### P3 - UI/UX 優化（必要項）
- [ ] 預覽與執行流程一致化（各模式同樣的確認勾選）
- [ ] 統計資訊與報表路徑固定展示區
- [ ] 操作清單與衝突清單視覺分區

### P4 - 測試與穩定性
- [ ] Unit tests：`core/dupe.py`, `core/actions.py`, `core/naming.py`
- [ ] Windows 權限錯誤測試（ACL/PermissionError）

## V3.0.0 Plan (攝影素材整理 MVP)

### M0 - 掃描與基礎分類
- [x] 新增攝影 preset（RAW/JPG/VIDEO/OTHERS），支援 JPG/HEIC
- [x] 掃描來源資料夾（含子資料夾），讀取基本檔案資訊

### M1 - EXIF/Metadata 支援
- [x] EXIF 拍攝時間解析（照片）
- [x] 影片拍攝時間/時長/解析度（可用檔案時間 fallback）
- [x] 時間來源優先序：EXIF > 檔案 mtime

### M2 - RAW/JPG 成對規則
- [x] 配對 key：`stem` + `stem+parent`
- [x] EXIF key（拍攝時間 + 輔助欄位）做為選配策略
- [x] pairs.csv / orphans.csv 產出

### M3 - 整理輸出與布局
- [x] 支援兩種輸出布局（參數切換）：
  - `/Output/YYYY-MM-DD/RAW|JPG|VIDEO`
  - `/Output/Pairs/DSC01234/RAW|JPG`
- [x] 命名衝突處理（沿用 resolve_destination）

### M4 - 重複檔案偵測 + 隔離桶
- [x] 三層重複偵測（size/partial/full hash）
- [x] 重複檔移動到 `/Output/Duplicates/`

### M5 - 執行與回復
- [x] 產生 actions_log.jsonl（可回復）
- [x] 預覽（dry-run）與執行一致化

### M6 - Streamlit UI
- [x] 新增「攝影素材整理」模式
- [x] 預覽表格 + 統計 + 確認勾選

## Done
- [x] Core module extraction (scanner/dupe/actions/report/types)
- [x] 3-layer matching (size -> partial hash -> full hash)
- [x] CLI additions: --report, --partial-size-mb, --full-hash
- [x] Strategy controls: --keep-strategy, --prefer-path, --move-scope
- [x] Strategy preview summary + clearer preview lists
- [x] Naming cleanup options (copy suffix/space/special + conflict suffix)
- [x] CSV report includes action/strategy/keep/move + conflict fields
- [x] Documentation updates (README/CLAUDE)
- [x] Tag and release prep: v1.1.0
- [x] Work-file organizer CLI + presets + time partitioning + duplicates quarantine
- [x] Streamlit UI (preview -> confirm -> execute)

## Next up
- [ ] Unit tests for core modules
- [ ] Permission error test harness (Windows ACL/SID)

## Optional/Backlog
- [ ] Release notes and version bump (v1.2.0)
