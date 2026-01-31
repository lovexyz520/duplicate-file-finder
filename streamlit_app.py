from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from core import (
    find_duplicates_between,
    move_duplicates,
    organize,
    scan_folder,
    write_duplicates_report,
    write_pairs_report,
    JPG_EXTS_DEFAULT,
    RAW_EXTS_DEFAULT,
    pair_by_stem,
    plan_pair_layout,
    execute_pair_actions,
    PairRecord,
    plan_photo_actions,
    execute_photo_actions,
    execute_duplicate_actions,
)
from rules_presets import WORK_PRESET, PHOTO_PRESET
from core.photo_executor import write_actions_log


# =============================================================================
# 設定檔路徑
# =============================================================================
SETTINGS_FILE = Path(__file__).parent / ".streamlit_settings.json"


# =============================================================================
# 設定儲存與載入
# =============================================================================


def _load_settings() -> dict[str, Any]:
    """載入使用者設定"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_settings(settings: dict[str, Any]) -> None:
    """儲存使用者設定"""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _get_setting(key: str, default: Any) -> Any:
    """取得設定值"""
    if "settings" not in st.session_state:
        st.session_state.settings = _load_settings()
    return st.session_state.settings.get(key, default)


def _set_setting(key: str, value: Any) -> None:
    """設定值並儲存"""
    if "settings" not in st.session_state:
        st.session_state.settings = _load_settings()
    st.session_state.settings[key] = value
    _save_settings(st.session_state.settings)


# =============================================================================
# 操作歷史記錄
# =============================================================================


def _add_history(mode: str, action: str, details: dict[str, Any]) -> None:
    """新增操作歷史"""
    if "history" not in st.session_state:
        st.session_state.history = []

    record = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "action": action,
        **details,
    }
    st.session_state.history.insert(0, record)

    # 只保留最近 20 筆
    st.session_state.history = st.session_state.history[:20]


def _show_history_sidebar() -> None:
    """在側邊欄顯示操作歷史"""
    if "history" not in st.session_state or not st.session_state.history:
        return

    with st.sidebar.expander("📜 操作歷史", expanded=False):
        for record in st.session_state.history[:5]:
            ts = datetime.fromisoformat(record["timestamp"])
            time_str = ts.strftime("%H:%M:%S")
            mode = record.get("mode", "")
            action = record.get("action", "")

            if action == "preview":
                st.caption(f"🔍 {time_str} - {mode} 預覽")
            elif action == "execute":
                count = record.get("count", 0)
                st.caption(f"✅ {time_str} - {mode} 執行 ({count})")


# =============================================================================
# 清除結果功能
# =============================================================================


def _init_results_state(key: str) -> None:
    """初始化結果狀態"""
    if f"{key}_results" not in st.session_state:
        st.session_state[f"{key}_results"] = None


def _set_results(key: str, results: dict[str, Any]) -> None:
    """設定結果"""
    st.session_state[f"{key}_results"] = results


def _get_results(key: str) -> dict[str, Any] | None:
    """取得結果"""
    return st.session_state.get(f"{key}_results")


def _clear_results(key: str) -> None:
    """清除結果"""
    st.session_state[f"{key}_results"] = None


def _clear_results_button(key: str) -> bool:
    """清除結果按鈕"""
    if _get_results(key):
        if st.button("🗑️ 清除結果", key=f"{key}_clear", help="清除預覽結果"):
            _clear_results(key)
            st.rerun()
            return True
    return False


# =============================================================================
# 進度條功能
# =============================================================================


def _count_files_estimate(folder: str, recursive: bool) -> int:
    """快速估算檔案數量"""
    count = 0
    try:
        if recursive:
            for root, _, files in os.walk(folder):
                count += len(files)
                if count > 10000:  # 超過 10000 就停止計數
                    return count
        else:
            count = len([f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))])
    except Exception:
        pass
    return count


def _show_file_estimate(folders: list[tuple[str, bool]]) -> None:
    """顯示檔案數量預估"""
    total = 0
    for folder, recursive in folders:
        if os.path.isdir(folder):
            total += _count_files_estimate(folder, recursive)

    if total > 0:
        st.info(f"📊 預估檔案數量：約 {total:,} 個" + ("+" if total >= 10000 else ""))


# =============================================================================
# 共用元件
# =============================================================================


def _select_with_mapping(
    label: str,
    options: list[tuple[str, str]],
    index: int = 0,
    key: str | None = None,
) -> str:
    """下拉選單，支援顯示文字與實際值的映射"""
    labels = [item[0] for item in options]
    values = [item[1] for item in options]
    selected = st.selectbox(label, labels, index=index, key=key)
    return values[labels.index(selected)]


def _ask_directory() -> str | None:
    """開啟系統資料夾選擇器"""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory()
        root.destroy()
        return path or None
    except Exception:
        return None


def _path_input(label: str, key: str, default: str, help_text: str = "") -> str:
    """路徑輸入元件，含資料夾選擇按鈕"""
    # 從設定載入預設值
    saved_value = _get_setting(f"path_{key}", default)
    if key not in st.session_state:
        st.session_state[key] = saved_value
    warning_key = f"{key}_browse_warning"

    def _on_browse() -> None:
        path = _ask_directory()
        if path:
            st.session_state[key] = path
            _set_setting(f"path_{key}", path)  # 儲存設定
            st.session_state.pop(warning_key, None)
        else:
            st.session_state[warning_key] = True

    col1, col2 = st.columns([5, 1])
    with col1:
        value = st.text_input(label, key=key, help=help_text)
        if st.session_state.get(warning_key):
            st.warning("無法開啟資料夾選擇器，請手動輸入路徑。")
    with col2:
        st.write("")  # 對齊用
        st.button("📁", key=f"{key}_browse", on_click=_on_browse, help="選擇資料夾")

    # 儲存變更
    if value != saved_value:
        _set_setting(f"path_{key}", value)

    return value


def _validate_path(path: str, label: str, must_exist: bool = True) -> bool:
    """驗證路徑是否有效"""
    if not path or not path.strip():
        st.error(f"請輸入{label}")
        return False
    if must_exist and not os.path.isdir(path):
        st.error(f"{label}不存在：{path}")
        return False
    return True


def _check_overlapping(folder1: str, folder2: str) -> str | None:
    """檢查兩個資料夾是否重疊"""
    path1 = os.path.abspath(folder1)
    path2 = os.path.abspath(folder2)
    if path1 == path2:
        return "same"
    path1_with_sep = path1 + os.sep
    path2_with_sep = path2 + os.sep
    if path2.startswith(path1_with_sep):
        return "folder1_contains_folder2"
    if path1.startswith(path2_with_sep):
        return "folder2_contains_folder1"
    return None


def _ops_to_table(rows: list[dict[str, Any]], height: int = 300) -> None:
    """顯示操作清單表格"""
    if rows:
        st.dataframe(rows, use_container_width=True, height=height)
    else:
        st.info("（無資料）")


def _show_metrics(metrics: list[tuple[str, Any, str | None]]) -> None:
    """顯示統計指標卡片"""
    cols = st.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        with col:
            st.metric(label=label, value=value, delta=delta)


def _confirm_checkbox(label: str, key: str) -> bool:
    """帶警告樣式的確認勾選框"""
    st.warning("⚠️ 請確認後再執行")
    return st.checkbox(label, value=False, key=key)


def _show_report_paths(paths: list[tuple[str, str]]) -> None:
    """顯示報表路徑"""
    with st.container():
        st.markdown("**📄 報表輸出：**")
        for label, path in paths:
            st.code(f"{label}: {path}", language=None)


def _show_success_message(message: str) -> None:
    """顯示醒目的成功訊息"""
    st.balloons()
    st.success(message)
    st.toast(message, icon="✅")


def _clean_settings_ui(key_prefix: str) -> tuple[bool, bool, bool, bool, int]:
    """檔名清理設定區塊（共用）"""
    with st.expander("🧹 檔名清理設定", expanded=False):
        clean_names = st.checkbox(
            "啟用全部清理（移除副本後綴、空白正規化、移除特殊字元）",
            value=False,
            key=f"{key_prefix}_clean_names",
        )
        st.caption("或選擇個別項目：")
        col1, col2, col3 = st.columns(3)
        with col1:
            clean_copy_suffix = st.checkbox(
                "移除 (1)/(2)", value=False, key=f"{key_prefix}_clean_copy"
            )
        with col2:
            clean_normalize_space = st.checkbox(
                "空白正規化", value=False, key=f"{key_prefix}_clean_space"
            )
        with col3:
            clean_remove_special = st.checkbox(
                "移除特殊字元", value=False, key=f"{key_prefix}_clean_special"
            )
        conflict_width = st.number_input(
            "衝突補碼位數", min_value=0, value=3, key=f"{key_prefix}_conflict"
        )
    return clean_names, clean_copy_suffix, clean_normalize_space, clean_remove_special, int(conflict_width)


def _dupe_settings_ui(key_prefix: str) -> tuple[str, str, int, str]:
    """重複檔案偵測設定區塊（共用）"""
    with st.expander("🔍 重複檔案偵測設定", expanded=False):
        dupe_strategy = _select_with_mapping(
            "保留策略",
            [
                ("保留最新修改時間", "latest"),
                ("保留最早建立時間", "earliest"),
                ("優先保留指定資料夾", "prefer-path"),
            ],
            index=0,
            key=f"{key_prefix}_dupe_strategy",
        )
        prefer_path = ""
        if dupe_strategy == "prefer-path":
            prefer_path = _path_input(
                "優先保留的資料夾",
                f"{key_prefix}_prefer_path",
                "",
                help_text="重複檔案中，此資料夾內的檔案會優先被保留",
            )

        col1, col2 = st.columns(2)
        with col1:
            partial_size_mb = st.number_input(
                "partial hash 大小（MB）",
                min_value=1,
                value=1,
                key=f"{key_prefix}_partial_mb",
            )
        with col2:
            full_hash = _select_with_mapping(
                "完整 hash 演算法",
                [("SHA256（安全）", "sha256"), ("xxhash64（快速）", "xxhash64")],
                index=0,
                key=f"{key_prefix}_full_hash",
            )
    return dupe_strategy, prefer_path, int(partial_size_mb), full_hash


def _parse_exts_text(value: str, defaults: set[str]) -> set[str]:
    """解析副檔名文字"""
    items = {v.strip().lower() for v in value.split(",") if v.strip()}
    if not items:
        return defaults
    normalized = set()
    for ext in items:
        normalized.add(ext if ext.startswith(".") else f".{ext}")
    return normalized


def _show_image_preview(file_path: str) -> None:
    """顯示圖片預覽"""
    ext = os.path.splitext(file_path)[1].lower()
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    if ext in image_exts and os.path.exists(file_path):
        try:
            st.image(file_path, width=200, caption=os.path.basename(file_path))
        except Exception:
            pass


# =============================================================================
# 模式 1：重複檔案偵測
# =============================================================================


def duplicate_finder_ui() -> None:
    st.header("🔍 重複檔案偵測")

    _init_results_state("dupe")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
1. 選擇「資料夾 1 / 資料夾 2」與輸出資料夾
2. 建議先按「一鍵預覽」確認移動清單與衝突清單
3. 若要實際移動，勾選確認後再按「執行移動」
4. 報表會輸出到輸出資料夾的 `duplicates_report.csv`
        """)

    with st.expander("❓ 常見問題", expanded=False):
        st.markdown("""
- **資料夾重疊**：若兩資料夾互為子資料夾，結果可能不準確
- **優先保留指定資料夾**：重複檔案中，指定資料夾內的檔案會優先被保留
- **命名衝突**：若輸出資料夾已有同名檔案，會自動加上 `_001`
        """)

    # 路徑輸入
    st.subheader("📂 資料夾設定")
    col1, col2 = st.columns(2)
    with col1:
        folder1 = _path_input("資料夾 1", "dupe_folder1", "folder1")
    with col2:
        folder2 = _path_input("資料夾 2", "dupe_folder2", "folder2")
    output_folder = _path_input("輸出資料夾", "dupe_output", "output_folder")

    recursive = st.checkbox("🔄 遞迴掃描子資料夾", value=False)

    # 檔案數量預估
    if os.path.isdir(folder1) or os.path.isdir(folder2):
        _show_file_estimate([(folder1, recursive), (folder2, recursive)])

    # 比對設定
    with st.expander("⚙️ 比對設定", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            partial_size_mb = st.number_input(
                "partial hash 大小（MB）", min_value=1, value=1
            )
        with col2:
            full_hash = _select_with_mapping(
                "完整 hash 演算法",
                [("SHA256（安全）", "sha256"), ("xxhash64（快速）", "xxhash64")],
                index=0,
            )

    # 保留策略
    with st.expander("🎯 保留策略", expanded=False):
        keep_strategy = _select_with_mapping(
            "保留策略",
            [
                ("保留資料夾 1", "folder1"),
                ("保留資料夾 2", "folder2"),
                ("保留最新修改時間", "latest"),
                ("保留最早建立時間", "earliest"),
                ("優先保留指定資料夾", "prefer-path"),
            ],
            index=0,
        )
        prefer_path = ""
        if keep_strategy == "prefer-path":
            prefer_path = _path_input(
                "優先保留的資料夾",
                "dupe_prefer_path",
                "",
                help_text="重複檔案中，此資料夾內的檔案會優先被保留",
            )

        move_scope = _select_with_mapping(
            "移動範圍",
            [("只移動資料夾 2", "folder2"), ("兩邊都可移動", "both")],
            index=0,
        )

    # 檔名清理
    clean_names, clean_copy_suffix, clean_normalize_space, clean_remove_special, conflict_width = _clean_settings_ui("dupe")

    st.divider()

    # 確認與執行
    confirm = _confirm_checkbox("我了解這將移動檔案", "dupe_confirm")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        preview_clicked = st.button("👁️ 一鍵預覽", use_container_width=True)
    with col2:
        execute_clicked = st.button(
            "▶️ 執行移動",
            disabled=not confirm,
            use_container_width=True,
            type="primary",
        )
    with col3:
        _clear_results_button("dupe")

    # 預覽邏輯
    if preview_clicked:
        if keep_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return
        if not _validate_path(folder1, "資料夾 1") or not _validate_path(folder2, "資料夾 2"):
            return
        if not _validate_path(output_folder, "輸出資料夾", must_exist=False):
            return

        overlap = _check_overlapping(folder1, folder2)
        if overlap is not None:
            st.warning(f"⚠️ 資料夾重疊：{overlap}")

        progress_bar = st.progress(0, text="掃描資料夾 1...")

        files1 = scan_folder(folder1, recursive)
        progress_bar.progress(30, text="掃描資料夾 2...")

        files2 = scan_folder(folder2, recursive)
        progress_bar.progress(50, text="比對檔案...")

        matches = find_duplicates_between(
            files1,
            files2,
            partial_bytes=int(partial_size_mb) * 1024 * 1024,
            full_hash_algo=full_hash,
        )
        progress_bar.progress(80, text="規劃移動...")

        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )
        effective_conflict_width = conflict_width if clean_enabled else 1
        _, operations = move_duplicates(
            matches,
            output_folder,
            dry_run=True,
            keep_strategy=keep_strategy,
            prefer_path=prefer_path if prefer_path else None,
            move_scope=move_scope,
            clean_names=clean_enabled,
            clean_copy_suffix=clean_copy_suffix or clean_names,
            clean_normalize_space=clean_normalize_space or clean_names,
            clean_remove_special=clean_remove_special or clean_names,
            conflict_suffix_width=effective_conflict_width,
        )

        progress_bar.progress(100, text="完成！")

        # 統計結果
        keep_rows = []
        move_rows = []
        conflict_rows = []
        for op in operations:
            if op.action == "kept_by_strategy":
                keep_rows.append({"keep_path": op.keep_path, "strategy": op.strategy})
                continue
            source = op.duplicate.path if op.keep_path != op.duplicate.path else op.original.path
            move_rows.append({"source": source, "dest": op.move_path})
            if op.name_conflict and op.desired_move_path:
                conflict_rows.append(
                    {"source": source, "desired": op.desired_move_path, "final": op.move_path}
                )

        # 儲存結果
        _set_results("dupe", {
            "matches": matches,
            "operations": operations,
            "keep_rows": keep_rows,
            "move_rows": move_rows,
            "conflict_rows": conflict_rows,
        })

        _add_history("重複檔案偵測", "preview", {"count": len(matches)})

    # 顯示結果
    results = _get_results("dupe")
    if results:
        st.success("預覽完成！")
        _show_metrics([
            ("重複檔案", len(results["matches"]), None),
            ("保留", len(results["keep_rows"]), None),
            ("將移動", len(results["move_rows"]), None),
            ("命名衝突", len(results["conflict_rows"]), "⚠️" if results["conflict_rows"] else None),
        ])

        report_path = os.path.join(output_folder, "duplicates_report.csv")
        os.makedirs(output_folder, exist_ok=True)
        write_duplicates_report(results["matches"], report_path, actions=results["operations"])
        _show_report_paths([("重複檔案報表", report_path)])

        with st.expander("📋 保留清單", expanded=False):
            _ops_to_table(results["keep_rows"])
        with st.expander("📋 移動清單", expanded=True):
            _ops_to_table(results["move_rows"])
        with st.expander("⚠️ 衝突清單", expanded=len(results["conflict_rows"]) > 0):
            _ops_to_table(results["conflict_rows"])

    # 執行邏輯
    if execute_clicked:
        if keep_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return
        if not _validate_path(folder1, "資料夾 1") or not _validate_path(folder2, "資料夾 2"):
            return
        if not _validate_path(output_folder, "輸出資料夾", must_exist=False):
            return

        progress_bar = st.progress(0, text="掃描中...")

        files1 = scan_folder(folder1, recursive)
        progress_bar.progress(30, text="掃描資料夾 2...")

        files2 = scan_folder(folder2, recursive)
        progress_bar.progress(50, text="比對檔案...")

        matches = find_duplicates_between(
            files1,
            files2,
            partial_bytes=int(partial_size_mb) * 1024 * 1024,
            full_hash_algo=full_hash,
        )
        progress_bar.progress(70, text="移動檔案...")

        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )
        effective_conflict_width = conflict_width if clean_enabled else 1
        moved_count, operations = move_duplicates(
            matches,
            output_folder,
            dry_run=False,
            keep_strategy=keep_strategy,
            prefer_path=prefer_path if prefer_path else None,
            move_scope=move_scope,
            clean_names=clean_enabled,
            clean_copy_suffix=clean_copy_suffix or clean_names,
            clean_normalize_space=clean_normalize_space or clean_names,
            clean_remove_special=clean_remove_special or clean_names,
            conflict_suffix_width=effective_conflict_width,
        )

        progress_bar.progress(90, text="產生報表...")
        report_path = os.path.join(output_folder, "duplicates_report.csv")
        write_duplicates_report(matches, report_path, actions=operations)

        progress_bar.progress(100, text="完成！")

        _add_history("重複檔案偵測", "execute", {"count": moved_count})
        _clear_results("dupe")
        _show_success_message(f"✅ 已移動 {moved_count} 個檔案")
        _show_report_paths([("報表", report_path)])


# =============================================================================
# 模式 2：工作檔案整理
# =============================================================================


def organizer_ui() -> None:
    st.header("📁 工作檔案整理助手")

    _init_results_state("org")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
1. 選擇來源資料夾與輸出資料夾
2. 依需求開啟：遞迴掃描 / 時間分層 / 重複檔案偵測
3. 建議先按「一鍵預覽」確認整理清單
4. 勾選確認後再按「執行整理」
        """)

    with st.expander("❓ 常見問題", expanded=False):
        st.markdown("""
- **Duplicates/**：重複檔案會移到輸出資料夾內的 `Duplicates/`
- **時間分層**：會依檔案修改時間分到 `/YYYY-MM/分類`
- **命名衝突**：若目的地已有同名檔案，會自動加上 `_001`
        """)

    # 路徑設定
    st.subheader("📂 資料夾設定")
    source = _path_input("來源資料夾", "org_source", ".")
    output = _path_input("輸出資料夾", "org_output", "organized_output")

    # 掃描選項
    col1, col2, col3 = st.columns(3)
    with col1:
        recursive = st.checkbox("🔄 遞迴掃描", value=True)
    with col2:
        time_partition = st.checkbox("📅 時間分層", value=False)
    with col3:
        enable_duplicates = st.checkbox("🔍 偵測重複", value=True)

    # 檔案數量預估
    if os.path.isdir(source):
        _show_file_estimate([(source, recursive)])

    skip_duplicates = not enable_duplicates

    # 重複檔案設定
    if enable_duplicates:
        dupe_strategy, prefer_path, partial_size_mb, full_hash = _dupe_settings_ui("org")
    else:
        dupe_strategy, prefer_path, partial_size_mb, full_hash = "latest", "", 1, "sha256"

    # 檔名清理
    clean_names, clean_copy_suffix, clean_normalize_space, clean_remove_special, conflict_width = _clean_settings_ui("org")

    st.divider()

    # 確認與執行
    confirm = _confirm_checkbox("我了解這將移動檔案", "org_confirm")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        preview_clicked = st.button("👁️ 一鍵預覽", key="org_preview", use_container_width=True)
    with col2:
        execute_clicked = st.button(
            "▶️ 執行整理",
            disabled=not confirm,
            key="org_execute",
            use_container_width=True,
            type="primary",
        )
    with col3:
        _clear_results_button("org")

    if preview_clicked:
        if enable_duplicates and dupe_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return
        if not _validate_path(source, "來源資料夾"):
            return
        if not _validate_path(output, "輸出資料夾", must_exist=False):
            return

        progress_bar = st.progress(0, text="掃描檔案...")

        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )
        effective_conflict_width = conflict_width if clean_enabled else 1

        progress_bar.progress(30, text="分析檔案...")

        total_files, duplicate_matches, _, organize_actions = organize(
            source_folder=source,
            output_folder=output,
            recursive=recursive,
            time_partition=time_partition,
            dry_run=True,
            skip_duplicates=skip_duplicates,
            dupe_strategy=dupe_strategy,
            prefer_path=prefer_path if prefer_path else None,
            partial_size_mb=partial_size_mb,
            full_hash_algo=full_hash,
            clean_names=clean_enabled,
            clean_copy_suffix=clean_copy_suffix or clean_names,
            clean_normalize_space=clean_normalize_space or clean_names,
            clean_remove_special=clean_remove_special or clean_names,
            conflict_suffix_width=effective_conflict_width,
            preset=WORK_PRESET,
        )

        progress_bar.progress(100, text="完成！")

        org_rows = [
            {
                "來源": a.source_path,
                "目的地": a.dest_path,
                "分類": a.category,
                "衝突": "⚠️" if a.name_conflict else "",
            }
            for a in organize_actions
        ]

        _set_results("org", {
            "total_files": total_files,
            "duplicate_matches": duplicate_matches,
            "organize_actions": organize_actions,
            "org_rows": org_rows,
        })

        _add_history("工作檔案整理", "preview", {"count": total_files})

    # 顯示結果
    results = _get_results("org")
    if results:
        st.success("預覽完成！")
        _show_metrics([
            ("來源檔案", results["total_files"], None),
            ("重複檔案", len(results["duplicate_matches"]), None),
            ("整理項目", len(results["organize_actions"]), None),
        ])

        _show_report_paths([("整理報表", os.path.join(output, "organize_report.csv"))])

        with st.expander("📋 整理清單", expanded=True):
            _ops_to_table(results["org_rows"], height=400)

    if execute_clicked:
        if enable_duplicates and dupe_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return
        if not _validate_path(source, "來源資料夾"):
            return
        if not _validate_path(output, "輸出資料夾", must_exist=False):
            return

        progress_bar = st.progress(0, text="掃描檔案...")

        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )
        effective_conflict_width = conflict_width if clean_enabled else 1

        progress_bar.progress(30, text="整理檔案...")

        total_files, duplicate_matches, _, organize_actions = organize(
            source_folder=source,
            output_folder=output,
            recursive=recursive,
            time_partition=time_partition,
            dry_run=False,
            skip_duplicates=skip_duplicates,
            dupe_strategy=dupe_strategy,
            prefer_path=prefer_path if prefer_path else None,
            partial_size_mb=partial_size_mb,
            full_hash_algo=full_hash,
            clean_names=clean_enabled,
            clean_copy_suffix=clean_copy_suffix or clean_names,
            clean_normalize_space=clean_normalize_space or clean_names,
            clean_remove_special=clean_remove_special or clean_names,
            conflict_suffix_width=effective_conflict_width,
            preset=WORK_PRESET,
        )

        progress_bar.progress(100, text="完成！")

        _add_history("工作檔案整理", "execute", {"count": len(organize_actions)})
        _clear_results("org")
        _show_success_message(f"✅ 整理完成！來源 {total_files} 個，整理 {len(organize_actions)} 個，重複 {len(duplicate_matches)} 個")


# =============================================================================
# 模式 3：RAW/JPG 配對工具
# =============================================================================


def pairing_ui() -> None:
    st.header("📷 RAW/JPG 配對工具")

    _init_results_state("pair")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
1. 選擇 JPG 與 RAW 資料夾，並設定輸出資料夾
2. 選擇模式：只複製 RAW 或成對整理
3. 建議先按「一鍵預覽」，確認 pairs / orphans 清單
4. 勾選確認後再執行
        """)

    # 路徑設定
    st.subheader("📂 資料夾設定")
    col1, col2 = st.columns(2)
    with col1:
        jpg_folder = _path_input("JPG 資料夾", "pair_jpg", "folder1")
    with col2:
        raw_folder = _path_input("RAW 資料夾", "pair_raw", "folder2")
    output_folder = _path_input("輸出資料夾", "pair_output", "pair_output")

    # 模式設定
    st.subheader("⚙️ 配對設定")
    col1, col2 = st.columns(2)
    with col1:
        mode = _select_with_mapping(
            "模式",
            [("只複製 RAW", "copy-raw"), ("成對整理", "pair-organize")],
            index=0,
        )
    with col2:
        key_mode = _select_with_mapping(
            "配對 key",
            [("檔名（stem）", "stem"), ("檔名 + 父資料夾", "stem+parent")],
            index=0,
        )

    recursive = st.checkbox("🔄 遞迴掃描子資料夾", value=False)

    # 檔案數量預估
    if os.path.isdir(jpg_folder) or os.path.isdir(raw_folder):
        _show_file_estimate([(jpg_folder, recursive), (raw_folder, recursive)])

    # 副檔名設定
    with st.expander("📝 副檔名設定", expanded=False):
        jpg_exts_text = st.text_input(
            "JPG 副檔名（逗號分隔）",
            value=",".join(sorted(JPG_EXTS_DEFAULT)),
        )
        raw_exts_text = st.text_input(
            "RAW 副檔名（逗號分隔）",
            value=",".join(sorted(RAW_EXTS_DEFAULT)),
        )

    # 成對整理設定
    with st.expander("📁 成對整理布局（pair-organize 模式）", expanded=False):
        layout = _select_with_mapping(
            "整理布局",
            [
                ("RAW/JPG 同資料夾", "raw-with-jpg"),
                ("每張一資料夾", "per-pair-folder"),
                ("RAW/JPG 分開 + pairs.csv", "split-index"),
            ],
            index=0,
        )
        use_move = st.checkbox("使用移動（Move）而非複製", value=False)

    st.divider()

    # 確認與執行
    confirm = _confirm_checkbox("我了解這將複製/移動檔案", "pair_confirm")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        preview_clicked = st.button("👁️ 一鍵預覽", use_container_width=True)
    with col2:
        execute_clicked = st.button(
            "▶️ 執行",
            disabled=not confirm,
            use_container_width=True,
            type="primary",
        )
    with col3:
        _clear_results_button("pair")

    if preview_clicked:
        if not _validate_path(jpg_folder, "JPG 資料夾") or not _validate_path(raw_folder, "RAW 資料夾"):
            return
        if not _validate_path(output_folder, "輸出資料夾", must_exist=False):
            return

        progress_bar = st.progress(0, text="掃描 JPG...")

        jpg_exts = _parse_exts_text(jpg_exts_text, JPG_EXTS_DEFAULT)
        raw_exts = _parse_exts_text(raw_exts_text, RAW_EXTS_DEFAULT)

        progress_bar.progress(50, text="掃描 RAW...")

        pairs, orphan_jpgs, orphan_raws = pair_by_stem(
            jpg_folder,
            raw_folder,
            recursive=recursive,
            jpg_exts=jpg_exts,
            raw_exts=raw_exts,
            key_mode=key_mode,
        )

        progress_bar.progress(100, text="完成！")

        pair_rows = [{"key": p.key, "JPG": p.jpg_path, "RAW": p.raw_path} for p in pairs]
        orphan_rows = (
            [{"類型": "JPG", "路徑": p} for p in orphan_jpgs]
            + [{"類型": "RAW", "路徑": p} for p in orphan_raws]
        )

        _set_results("pair", {
            "pairs": pairs,
            "orphan_jpgs": orphan_jpgs,
            "orphan_raws": orphan_raws,
            "pair_rows": pair_rows,
            "orphan_rows": orphan_rows,
        })

        _add_history("RAW/JPG 配對", "preview", {"count": len(pairs)})

    # 顯示結果
    results = _get_results("pair")
    if results:
        st.success("預覽完成！")
        _show_metrics([
            ("配對成功", len(results["pairs"]), None),
            ("孤兒 JPG", len(results["orphan_jpgs"]), "⚠️" if results["orphan_jpgs"] else None),
            ("孤兒 RAW", len(results["orphan_raws"]), "⚠️" if results["orphan_raws"] else None),
        ])

        os.makedirs(output_folder, exist_ok=True)
        report_pairs = os.path.join(output_folder, "pairs.csv")
        report_orphans = os.path.join(output_folder, "orphans.csv")
        write_pairs_report(results["pairs"], results["orphan_jpgs"], results["orphan_raws"], report_pairs, report_orphans)
        _show_report_paths([("配對報表", report_pairs), ("孤兒報表", report_orphans)])

        # 圖片預覽
        if results["pairs"]:
            with st.expander("🖼️ 圖片預覽", expanded=False):
                preview_cols = st.columns(min(4, len(results["pairs"])))
                for i, p in enumerate(results["pairs"][:4]):
                    with preview_cols[i]:
                        _show_image_preview(p.jpg_path)

        with st.expander("📋 Pairs 清單", expanded=True):
            _ops_to_table(results["pair_rows"])
        with st.expander("📋 Orphans 清單", expanded=len(results["orphan_rows"]) > 0):
            _ops_to_table(results["orphan_rows"])

    if execute_clicked:
        if not _validate_path(jpg_folder, "JPG 資料夾") or not _validate_path(raw_folder, "RAW 資料夾"):
            return
        if not _validate_path(output_folder, "輸出資料夾", must_exist=False):
            return

        progress_bar = st.progress(0, text="掃描檔案...")

        jpg_exts = _parse_exts_text(jpg_exts_text, JPG_EXTS_DEFAULT)
        raw_exts = _parse_exts_text(raw_exts_text, RAW_EXTS_DEFAULT)
        pairs, orphan_jpgs, orphan_raws = pair_by_stem(
            jpg_folder,
            raw_folder,
            recursive=recursive,
            jpg_exts=jpg_exts,
            raw_exts=raw_exts,
            key_mode=key_mode,
        )

        progress_bar.progress(40, text="產生報表...")

        os.makedirs(output_folder, exist_ok=True)
        report_pairs = os.path.join(output_folder, "pairs.csv")
        report_orphans = os.path.join(output_folder, "orphans.csv")
        write_pairs_report(pairs, orphan_jpgs, orphan_raws, report_pairs, report_orphans)

        progress_bar.progress(60, text="執行配對...")

        if mode == "copy-raw":
            actions = plan_pair_layout(
                pairs, output_folder, layout="raw-with-jpg", action="copy", conflict_suffix_width=3
            )
            raw_actions = [a for a in actions if a.role == "raw"]
            copied, _ = execute_pair_actions(raw_actions, dry_run=False, move=False)

            progress_bar.progress(100, text="完成！")

            _add_history("RAW/JPG 配對", "execute", {"count": copied})
            _clear_results("pair")
            _show_success_message(f"✅ 完成 RAW 複製：{copied} 個")
            return

        actions = plan_pair_layout(
            pairs,
            output_folder,
            layout=layout,
            action="move" if use_move else "copy",
            conflict_suffix_width=3,
        )
        copied, _ = execute_pair_actions(actions, dry_run=False, move=use_move)

        progress_bar.progress(100, text="完成！")

        _add_history("RAW/JPG 配對", "execute", {"count": copied})
        _clear_results("pair")
        _show_success_message(f"✅ 完成成對整理：{copied} 個")


# =============================================================================
# 模式 4：攝影素材整理
# =============================================================================


def photo_organizer_ui() -> None:
    st.header("🎞️ 攝影素材整理")

    _init_results_state("photo")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
1. 選擇來源與輸出資料夾
2. 選擇配對 key 與輸出布局
3. 可選擇是否啟用重複檔案偵測
4. 建議先按「一鍵預覽」，查看 pairs / orphans / duplicates
5. 勾選確認後執行
        """)

    # 路徑設定
    st.subheader("📂 資料夾設定")
    source = _path_input("來源資料夾", "photo_source", ".")
    output = _path_input("輸出資料夾", "photo_output", "photo_output")

    recursive = st.checkbox("🔄 遞迴掃描子資料夾", value=True)

    # 檔案數量預估
    if os.path.isdir(source):
        _show_file_estimate([(source, recursive)])

    # 配對與輸出
    st.subheader("⚙️ 配對與輸出")
    col1, col2 = st.columns(2)
    with col1:
        layout = _select_with_mapping(
            "輸出布局",
            [
                ("依日期/類型分類", "by-date-type"),
                ("每張一資料夾", "per-pair-folder"),
            ],
            index=0,
        )
    with col2:
        pair_key = _select_with_mapping(
            "配對 key",
            [
                ("檔名（stem）", "stem"),
                ("檔名 + 父資料夾", "stem+parent"),
                ("EXIF 拍攝時間", "exif"),
            ],
            index=0,
        )

    # 重複檔案偵測
    enable_duplicates = st.checkbox("🔍 啟用重複檔案偵測", value=True)

    if enable_duplicates:
        dupe_strategy, prefer_path, partial_size_mb, full_hash = _dupe_settings_ui("photo")
    else:
        dupe_strategy, prefer_path, partial_size_mb, full_hash = "latest", "", 1, "sha256"

    # 執行設定
    st.subheader("▶️ 執行設定")
    use_move = st.checkbox("使用移動（Move）而非複製", value=False)

    st.divider()

    # 確認與執行
    confirm = _confirm_checkbox("我了解這將移動/複製檔案", "photo_confirm")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        preview_clicked = st.button("👁️ 一鍵預覽", key="photo_preview", use_container_width=True)
    with col2:
        execute_clicked = st.button(
            "▶️ 執行整理",
            disabled=not confirm,
            key="photo_execute",
            use_container_width=True,
            type="primary",
        )
    with col3:
        _clear_results_button("photo")

    if preview_clicked:
        if not _validate_path(source, "來源資料夾"):
            return
        if not _validate_path(output, "輸出資料夾", must_exist=False):
            return
        if enable_duplicates and dupe_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return

        progress_bar = st.progress(0, text="掃描媒體檔案...")

        progress_bar.progress(30, text="分析配對...")

        plan = plan_photo_actions(
            source_folder=source,
            output_folder=output,
            recursive=recursive,
            preset=PHOTO_PRESET,
            layout=layout,
            pair_key_mode=pair_key,
            enable_duplicates=enable_duplicates,
            dupe_strategy=dupe_strategy,
            prefer_path=prefer_path if prefer_path else None,
            partial_size_mb=partial_size_mb,
            full_hash_algo=full_hash,
            conflict_suffix_width=3,
        )

        progress_bar.progress(100, text="完成！")

        pair_rows = [{"key": p[0], "JPG": p[1], "RAW": p[2]} for p in plan.pairs]
        orphan_rows = (
            [{"類型": "JPG", "路徑": p} for p in plan.orphan_jpgs]
            + [{"類型": "RAW", "路徑": p} for p in plan.orphan_raws]
        )

        _set_results("photo", {
            "plan": plan,
            "pair_rows": pair_rows,
            "orphan_rows": orphan_rows,
        })

        _add_history("攝影素材整理", "preview", {"count": len(plan.media_files)})

    # 顯示結果
    results = _get_results("photo")
    if results:
        plan = results["plan"]

        st.success("預覽完成！")
        _show_metrics([
            ("來源檔案", len(plan.media_files), None),
            ("配對成功", len(plan.pairs), None),
            ("孤兒 JPG", len(plan.orphan_jpgs), "⚠️" if plan.orphan_jpgs else None),
            ("孤兒 RAW", len(plan.orphan_raws), "⚠️" if plan.orphan_raws else None),
        ])
        _show_metrics([
            ("重複檔案", len(plan.duplicate_matches), None),
            ("整理項目", len(plan.photo_actions), None),
        ])

        os.makedirs(output, exist_ok=True)
        pairs_path = os.path.join(output, "pairs.csv")
        orphans_path = os.path.join(output, "orphans.csv")
        pair_records = [PairRecord(key=p[0], jpg_path=p[1], raw_path=p[2]) for p in plan.pairs]
        write_pairs_report(pair_records, plan.orphan_jpgs, plan.orphan_raws, pairs_path, orphans_path)

        report_paths = [("配對報表", pairs_path), ("孤兒報表", orphans_path)]
        if plan.duplicate_matches:
            duplicates_path = os.path.join(output, "duplicates_report.csv")
            write_duplicates_report(plan.duplicate_matches, duplicates_path, plan.duplicate_actions)
            report_paths.append(("重複報表", duplicates_path))
        _show_report_paths(report_paths)

        # 圖片預覽
        jpg_files = [p[1] for p in plan.pairs if p[1]][:4]
        if jpg_files:
            with st.expander("🖼️ 圖片預覽", expanded=False):
                preview_cols = st.columns(min(4, len(jpg_files)))
                for i, jpg_path in enumerate(jpg_files):
                    with preview_cols[i]:
                        _show_image_preview(jpg_path)

        with st.expander("📋 Pairs 清單", expanded=True):
            _ops_to_table(results["pair_rows"])
        with st.expander("📋 Orphans 清單", expanded=len(results["orphan_rows"]) > 0):
            _ops_to_table(results["orphan_rows"])

    if execute_clicked:
        if not _validate_path(source, "來源資料夾"):
            return
        if not _validate_path(output, "輸出資料夾", must_exist=False):
            return
        if enable_duplicates and dupe_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return

        progress_bar = st.progress(0, text="掃描媒體檔案...")

        progress_bar.progress(20, text="分析配對...")

        plan = plan_photo_actions(
            source_folder=source,
            output_folder=output,
            recursive=recursive,
            preset=PHOTO_PRESET,
            layout=layout,
            pair_key_mode=pair_key,
            enable_duplicates=enable_duplicates,
            dupe_strategy=dupe_strategy,
            prefer_path=prefer_path if prefer_path else None,
            partial_size_mb=partial_size_mb,
            full_hash_algo=full_hash,
            conflict_suffix_width=3,
        )

        progress_bar.progress(40, text="產生報表...")

        os.makedirs(output, exist_ok=True)
        pairs_path = os.path.join(output, "pairs.csv")
        orphans_path = os.path.join(output, "orphans.csv")
        pair_records = [PairRecord(key=p[0], jpg_path=p[1], raw_path=p[2]) for p in plan.pairs]
        write_pairs_report(pair_records, plan.orphan_jpgs, plan.orphan_raws, pairs_path, orphans_path)

        progress_bar.progress(60, text="處理重複檔案...")

        completed_duplicates = execute_duplicate_actions(plan.duplicate_actions, dry_run=False)

        progress_bar.progress(80, text="整理檔案...")

        completed_actions = execute_photo_actions(plan.photo_actions, dry_run=False, move=use_move)
        log_path = os.path.join(output, "actions_log.jsonl")
        write_actions_log(completed_actions, completed_duplicates, log_path)

        if plan.duplicate_matches:
            duplicates_path = os.path.join(output, "duplicates_report.csv")
            write_duplicates_report(plan.duplicate_matches, duplicates_path, plan.duplicate_actions)

        progress_bar.progress(100, text="完成！")

        _add_history("攝影素材整理", "execute", {"count": len(completed_actions)})
        _clear_results("photo")
        _show_success_message(f"✅ 已完成整理：{len(completed_actions)} 個檔案")


# =============================================================================
# 主程式
# =============================================================================


def main() -> None:
    st.set_page_config(
        page_title="檔案整理工具",
        page_icon="📁",
        layout="wide",
    )

    # 側邊欄模式選擇
    st.sidebar.title("📁 檔案整理工具")
    st.sidebar.markdown("---")

    mode = st.sidebar.radio(
        "選擇功能",
        [
            "🔍 重複檔案偵測",
            "📁 工作檔案整理",
            "📷 RAW/JPG 配對",
            "🎞️ 攝影素材整理",
        ],
        index=0,
        label_visibility="collapsed",
    )

    # 顯示操作歷史
    _show_history_sidebar()

    st.sidebar.markdown("---")
    st.sidebar.caption("v3.1.0 | 使用 Streamlit 建置")

    # 根據選擇顯示對應 UI
    if mode == "🔍 重複檔案偵測":
        duplicate_finder_ui()
    elif mode == "📁 工作檔案整理":
        organizer_ui()
    elif mode == "📷 RAW/JPG 配對":
        pairing_ui()
    else:
        photo_organizer_ui()


if __name__ == "__main__":
    main()
