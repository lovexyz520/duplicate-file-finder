# 檔案管理工具箱 v3.1.0

一套完整的檔案整理解決方案，包含重複檔案偵測、工作檔案分類、攝影素材配對與整理等功能，支援 CLI 與 Streamlit 圖形介面。

## 功能總覽

| 功能模組 | 說明 | CLI | UI |
|----------|------|-----|-----|
| 🔍 重複檔案偵測 | 比對兩個資料夾，找出並移動重複檔案 | ✅ | ✅ |
| 📁 工作檔案整理 | 依副檔名分類，支援時間分層與重複偵測 | ✅ | ✅ |
| 📷 RAW/JPG 配對 | 根據檔名配對 RAW 與 JPG，支援多種整理布局 | ✅ | ✅ |
| 🎞️ 攝影素材整理 | 日期分類、成對整理、重複檔案隔離 | ✅ | ✅ |

## 安裝

```bash
uv sync
```

## 快速開始

### Streamlit 圖形介面（推薦）

```bash
uv run streamlit run streamlit_app.py
```

啟動後在瀏覽器開啟 `http://localhost:8501`，透過側邊欄選擇功能模組。

### CLI 命令列

```bash
# 重複檔案偵測
uv run find_duplicates.py "C:\照片A" "C:\照片B" -o "C:\重複檔案" --dry-run

# 工作檔案整理
uv run organize_files.py "C:\Downloads" -o "C:\Organized" --dry-run

# RAW/JPG 配對
uv run pair_raw.py "C:\SelectedJPG" "C:\AllRAW" -o "C:\RAW_Selected" --dry-run

# 攝影素材整理
uv run photo_organize.py "C:\Photos\Incoming" -o "C:\Photos\Output" --dry-run
```

---

## 🔍 重複檔案偵測

比對兩個資料夾中的檔案，透過三層 hash 比對找出重複檔案，並依據保留策略決定保留或移動。

### 運作原理

```
1. 檔案大小比對 ─────→ 大小不同則跳過（效能優化）
        ↓
2. Partial Hash ─────→ 前/後 1MB 的 xxhash
        ↓
3. Full Hash ────────→ 完整 SHA256 或 xxhash64
        ↓
4. 依保留策略決定 ───→ 移動重複檔案到輸出資料夾
```

### CLI 使用範例

```bash
# 基本使用（預設 folder1, folder2 → output_folder）
uv run find_duplicates.py

# 指定資料夾與遞迴掃描
uv run find_duplicates.py "C:\照片A" "C:\照片B" -o "C:\重複檔案" -r

# 預覽模式（不實際移動）
uv run find_duplicates.py --dry-run

# 保留策略：最新修改時間
uv run find_duplicates.py --keep-strategy latest

# 保留策略：優先保留指定資料夾
uv run find_duplicates.py --keep-strategy prefer-path --prefer-path "C:\主資料庫"

# 移動範圍：雙向移動
uv run find_duplicates.py --keep-strategy latest --move-scope both

# 啟用檔名清理
uv run find_duplicates.py --clean-names

# 調整 hash 參數
uv run find_duplicates.py --partial-size-mb 2 --full-hash xxhash64
```

### 保留策略說明

| 策略 | 說明 |
|------|------|
| `folder1` | 保留資料夾 1 的檔案（預設） |
| `folder2` | 保留資料夾 2 的檔案 |
| `latest` | 保留修改時間較新的檔案 |
| `earliest` | 保留建立時間較早的檔案 |
| `prefer-path` | 優先保留指定資料夾內的檔案 |

### 參數說明

| 參數 | 說明 |
|------|------|
| `folder1` | 第一個資料夾路徑（預設：`folder1`） |
| `folder2` | 第二個資料夾路徑（預設：`folder2`） |
| `-o`, `--output` | 輸出資料夾路徑（預設：`output_folder`） |
| `-r`, `--recursive` | 遞迴掃描子資料夾 |
| `--dry-run` | 預覽模式，不實際移動檔案 |
| `--report` | 報表輸出路徑（預設：`output_folder/duplicates_report.csv`） |
| `--partial-size-mb` | partial hash 讀取前/後大小（MB，預設：1） |
| `--full-hash` | 完整 hash 演算法（`sha256` 或 `xxhash64`） |
| `--keep-strategy` | 保留策略（見上表） |
| `--prefer-path` | 保留策略為 `prefer-path` 時，優先保留的資料夾路徑 |
| `--move-scope` | 移動範圍（`folder2` 或 `both`；預設只移動 folder2） |
| `--clean-names` | 啟用檔名清理（移除(1)/(2)、空白正規化、移除特殊字元） |
| `--clean-copy-suffix` | 移除檔名結尾的 (1)/(2) 等副本後綴 |
| `--clean-normalize-space` | 空白正規化（多空白合併為一個） |
| `--clean-remove-special` | 移除檔名中的特殊字元 |
| `--clean-conflict-width` | 命名衝突自動補碼位數（預設：3） |

---

## 📁 工作檔案整理

將來源資料夾中的檔案依副檔名分類到對應的子資料夾，可選擇啟用時間分層與重複檔案偵測。

### 預設分類規則（WORK_PRESET）

| 類別 | 副檔名 |
|------|------|
| Docs | `.doc`, `.docx`, `.txt`, `.md` |
| PDF | `.pdf` |
| Sheets | `.xls`, `.xlsx`, `.csv` |
| Slides | `.ppt`, `.pptx` |
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.webp` |
| Videos | `.mp4`, `.mov`, `.avi`, `.mkv` |
| Archives | `.zip`, `.rar`, `.7z`, `.tar`, `.gz` |
| Code | `.py`, `.js`, `.json`, `.ts`, `.html`, `.css`, `.yml`, `.yaml` |
| Others | 其他未列出副檔名 |

### CLI 使用範例

```bash
# 基本整理
uv run organize_files.py "C:\Downloads" -o "C:\Organized"

# 遞迴掃描 + 時間分層（/YYYY-MM/分類/）
uv run organize_files.py "C:\Downloads" -o "C:\Organized" -r --time-partition

# 啟用檔名清理
uv run organize_files.py "C:\Downloads" -o "C:\Organized" --clean-names

# 略過重複檔案偵測
uv run organize_files.py "C:\Downloads" -o "C:\Organized" --skip-duplicates

# 重複檔案保留策略
uv run organize_files.py "C:\Downloads" -o "C:\Organized" --dupe-strategy latest
```

### 輸出結構

```
Organized/
├── 2024-01/
│   ├── Docs/
│   ├── Images/
│   └── ...
├── 2024-02/
│   └── ...
├── Duplicates/           # 重複檔案（若啟用偵測）
│   └── duplicates_report.csv
└── organize_report.csv   # 整理報表
```

---

## 📷 RAW/JPG 配對工具

當你只挑出滿意的 JPG 時，工具會自動找出對應的 RAW 檔並整理或複製。支援多種配對 key 與整理布局。

### 配對模式

| 模式 | 說明 |
|------|------|
| `copy-raw` | 僅複製配對成功的 RAW 檔到輸出資料夾 |
| `pair-organize` | 將配對的 RAW 與 JPG 一起整理 |

### 整理布局

| 布局 | 說明 |
|------|------|
| `raw-with-jpg` | RAW 與 JPG 放同資料夾（預設） |
| `per-pair-folder` | 每對檔案一個資料夾 |
| `split-index` | RAW/JPG 分開放 + pairs.csv 索引 |

### CLI 使用範例

```bash
# 模式 1：複製配對成功的 RAW
uv run pair_raw.py "C:\SelectedJPG" "C:\AllRAW" -o "C:\RAW_Selected"

# 模式 2：成對整理
uv run pair_raw.py "C:\JPG" "C:\RAW" -o "C:\Pairs" --mode pair-organize

# 每對一個資料夾
uv run pair_raw.py "C:\JPG" "C:\RAW" -o "C:\Pairs" --mode pair-organize --layout per-pair-folder

# 自訂副檔名
uv run pair_raw.py "C:\JPG" "C:\RAW" -o "C:\Pairs" --raw-exts ".ARW,.CR2,.NEF" --jpg-exts ".JPG,.HEIC"

# 使用 stem+parent 配對（避免同名衝突）
uv run pair_raw.py "C:\JPG" "C:\RAW" -o "C:\Pairs" --key-mode stem+parent
```

### 支援的副檔名

| 類型 | 預設副檔名 |
|------|-----------|
| RAW | `.arw`, `.cr2`, `.nef`, `.raf`, `.dng`, `.rw2` |
| JPG | `.jpg`, `.jpeg`, `.heic` |

---

## 🎞️ 攝影素材整理

專為攝影工作流設計，支援日期分類、RAW/JPG 成對整理、EXIF 讀取與重複檔案隔離。

### 預設分類規則（PHOTO_PRESET）

| 類別 | 副檔名 |
|------|------|
| RAW | `.arw`, `.cr2`, `.nef`, `.raf`, `.dng`, `.rw2` |
| JPG | `.jpg`, `.jpeg`, `.heic` |
| VIDEO | `.mp4`, `.mov`, `.avi`, `.mkv` |
| OTHERS | 其他 |

### CLI 使用範例

```bash
# 基本整理
uv run photo_organize.py "C:\Photos\Incoming" -o "C:\Photos\Output" -r

# 配對 key 使用 EXIF 拍攝時間
uv run photo_organize.py "C:\Photos\Incoming" -o "C:\Photos\Output" --pair-key exif

# 輸出布局：每對一資料夾
uv run photo_organize.py "C:\Photos\Incoming" -o "C:\Photos\Output" --layout per-pair-folder

# 關閉重複檔案偵測
uv run photo_organize.py "C:\Photos\Incoming" -o "C:\Photos\Output" --disable-duplicates

# 重複檔案保留策略
uv run photo_organize.py "C:\Photos\Incoming" -o "C:\Photos\Output" --dupe-strategy earliest
```

### 輸出結構

```
Output/
├── 2024-01-15/
│   ├── RAW/
│   │   └── DSC01234.ARW
│   └── JPG/
│       └── DSC01234.JPG
├── Duplicates/           # 重複檔案
├── pairs.csv             # 配對報表
├── orphans.csv           # 孤兒檔案報表
├── duplicates_report.csv # 重複檔案報表
└── actions_log.jsonl     # 執行日誌
```

---

## 🖥️ Streamlit 圖形介面

### 啟動方式

```bash
uv run streamlit run streamlit_app.py
```

### UI 功能特色

| 功能 | 說明 |
|------|------|
| 📊 進度條顯示 | 掃描與執行過程顯示即時進度 |
| 📈 預估檔案數 | 掃描前顯示預估檔案數量 |
| 👁️ 一鍵預覽 | 執行前先預覽結果，確認後再執行 |
| 🗑️ 清除結果 | 預覽後可清除結果重新設定 |
| 🎉 成功動畫 | 執行完成顯示動畫與 toast 通知 |
| 📜 操作歷史 | 側邊欄顯示最近 20 筆操作記錄 |
| 💾 設定自動儲存 | 常用設定自動儲存，下次開啟自動載入 |
| 📁 資料夾選擇器 | 點擊 📁 按鈕快速選擇資料夾 |
| 🖼️ 圖片預覽 | 攝影素材整理模式支援圖片預覽 |

---

## 📋 報表說明

### duplicates_report.csv（重複檔案報表）

| 欄位 | 說明 |
|------|------|
| `duplicate_path` | 被判定為重複的檔案路徑 |
| `original_path` | 保留參考的對應檔案路徑 |
| `size` | 檔案大小（bytes） |
| `mtime_duplicate` | 重複檔案的修改時間 |
| `mtime_original` | 原始檔案的修改時間 |
| `ctime_duplicate` | 重複檔案的建立時間 |
| `ctime_original` | 原始檔案的建立時間 |
| `partial_hash` | partial hash 值 |
| `full_hash` | 完整 hash 值 |
| `action` | `preview` / `moved` / `kept_by_strategy` |
| `strategy` | 使用的保留策略 |
| `keep_path` | 被保留的檔案路徑 |
| `move_path` | 被移動的檔案路徑 |
| `desired_move_path` | 原本想移動到的路徑（若有命名衝突） |
| `name_conflict` | 是否發生命名衝突（1/0） |

### organize_report.csv（整理報表）

| 欄位 | 說明 |
|------|------|
| `source_path` | 原始檔案路徑 |
| `dest_path` | 整理後路徑 |
| `desired_dest_path` | 原本想移動到的路徑（若有命名衝突） |
| `category` | 分類桶 |
| `action` | `preview` / `moved` |
| `name_conflict` | 是否發生命名衝突（1/0） |

### pairs.csv / orphans.csv（配對報表）

| 欄位 | 說明 |
|------|------|
| `key` | 配對 key（檔名 stem） |
| `jpg_path` | JPG 檔案路徑 |
| `raw_path` | RAW 檔案路徑 |
| `type` | `orphan_jpg` / `orphan_raw`（orphans.csv） |

---

## 📁 專案結構

```
duplicate-file-finder/
├── core/
│   ├── actions.py        # 移動重複檔案 + 衝突命名處理
│   ├── dupe.py           # 三層比對邏輯
│   ├── hashers.py        # partial hash / full hash
│   ├── naming.py         # 檔名清理與命名衝突處理
│   ├── organizer.py      # 工作檔案整理邏輯
│   ├── pairing.py        # RAW/JPG 配對工具
│   ├── media_scanner.py  # 攝影素材掃描 + metadata
│   ├── metadata.py       # EXIF / 影片 metadata
│   ├── photo_pairing.py  # 攝影素材成對
│   ├── photo_planner.py  # 攝影素材整理計畫
│   ├── photo_executor.py # 攝影素材執行 + log
│   ├── report.py         # CSV 報表輸出
│   ├── scanner.py        # 檔案掃描 / metadata
│   └── types.py          # 資料結構
├── find_duplicates.py    # 重複檔案 CLI
├── organize_files.py     # 工作檔案整理 CLI
├── pair_raw.py           # RAW/JPG 配對 CLI
├── photo_organize.py     # 攝影素材整理 CLI
├── rules_presets.py      # 分類規則 preset
├── streamlit_app.py      # Streamlit UI
├── pyproject.toml
└── README.md
```

---

## 依賴說明

| 套件 | 用途 |
|------|------|
| `xxhash` | 快速 partial hash 計算 |
| `streamlit` | 圖形介面 |
| `exifread` | EXIF 資訊讀取（攝影素材） |
| `hachoir` | 影片 metadata 讀取 |

---

## 注意事項

- ⚠️ 請先用 `--dry-run` 或「一鍵預覽」預覽結果後再執行
- Windows CMD 可能顯示中文亂碼（不影響功能）
- Streamlit UI 設定會自動儲存至 `.streamlit_settings.json`
- 建議定期備份重要檔案
