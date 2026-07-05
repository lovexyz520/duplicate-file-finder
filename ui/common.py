"""Streamlit UI 共用元件與狀態管理。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import streamlit as st

SETTINGS_FILE = Path(__file__).parent.parent / ".streamlit_settings.json"

DEFAULT_EXCLUDE_DIRS = ".git, node_modules, __pycache__, .venv, $RECYCLE.BIN, System Volume Information"


# =============================================================================
# 設定儲存與載入
# =============================================================================


def _load_settings() -> dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_settings(settings: dict[str, Any]) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_setting(key: str, default: Any) -> Any:
    if "settings" not in st.session_state:
        st.session_state.settings = _load_settings()
    return st.session_state.settings.get(key, default)


def set_setting(key: str, value: Any) -> None:
    if "settings" not in st.session_state:
        st.session_state.settings = _load_settings()
    st.session_state.settings[key] = value
    _save_settings(st.session_state.settings)


# =============================================================================
# 操作歷史記錄（含 undo log 路徑）
# =============================================================================


def add_history(
    mode: str,
    action: str,
    details: dict[str, Any],
    log_path: str | None = None,
) -> None:
    if "history" not in st.session_state:
        st.session_state.history = []

    record = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "action": action,
        **details,
    }
    if log_path:
        record["log_path"] = log_path
        known = get_setting("undo_logs", [])
        known = [log_path] + [p for p in known if p != log_path]
        set_setting("undo_logs", known[:20])
    st.session_state.history.insert(0, record)
    st.session_state.history = st.session_state.history[:20]


def known_undo_logs() -> list[str]:
    return [p for p in get_setting("undo_logs", []) if os.path.isfile(p)]


def show_history_sidebar() -> None:
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
            elif action == "undo":
                count = record.get("count", 0)
                st.caption(f"↩️ {time_str} - {mode} 還原 ({count})")


# =============================================================================
# 結果狀態
# =============================================================================


def init_results_state(key: str) -> None:
    if f"{key}_results" not in st.session_state:
        st.session_state[f"{key}_results"] = None


def set_results(key: str, results: dict[str, Any]) -> None:
    st.session_state[f"{key}_results"] = results


def get_results(key: str) -> dict[str, Any] | None:
    return st.session_state.get(f"{key}_results")


def clear_results(key: str) -> None:
    st.session_state[f"{key}_results"] = None


def clear_results_button(key: str) -> None:
    if get_results(key):
        if st.button("🗑️ 清除結果", key=f"{key}_clear", help="清除預覽結果"):
            clear_results(key)
            st.rerun()


# =============================================================================
# 進度條
# =============================================================================


class ProgressBar:
    """把多階段的 (done, total) callback 映射到單一 st.progress。"""

    def __init__(self) -> None:
        self._bar = st.progress(0, text="準備中...")

    def stage(
        self, label: str, start: float, end: float
    ) -> Callable[[int, int], None]:
        span = end - start

        def _callback(done: int, total: int) -> None:
            if total <= 0:
                fraction = end
            else:
                fraction = start + span * min(done / total, 1.0)
            self._bar.progress(
                min(int(fraction * 100), 100), text=f"{label}（{done}/{total}）"
            )

        return _callback

    def set(self, fraction: float, text: str) -> None:
        self._bar.progress(min(int(fraction * 100), 100), text=text)

    def done(self, text: str = "完成！") -> None:
        self._bar.progress(100, text=text)


def count_files_estimate(folder: str, recursive: bool) -> int:
    count = 0
    try:
        if recursive:
            for _, _, files in os.walk(folder):
                count += len(files)
                if count > 10000:
                    return count
        else:
            count = len(
                [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
            )
    except Exception:
        pass
    return count


def show_file_estimate(folders: list[tuple[str, bool]]) -> None:
    total = 0
    for folder, recursive in folders:
        if os.path.isdir(folder):
            total += count_files_estimate(folder, recursive)

    if total > 0:
        st.info(f"📊 預估檔案數量：約 {total:,} 個" + ("+" if total >= 10000 else ""))


# =============================================================================
# 輸入元件
# =============================================================================


def select_with_mapping(
    label: str,
    options: list[tuple[str, str]],
    index: int = 0,
    key: str | None = None,
) -> str:
    labels = [item[0] for item in options]
    values = [item[1] for item in options]
    selected = st.selectbox(label, labels, index=index, key=key)
    return values[labels.index(selected)]


def _ask_directory() -> str | None:
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


def path_input(label: str, key: str, default: str, help_text: str = "") -> str:
    saved_value = get_setting(f"path_{key}", default)
    if key not in st.session_state:
        st.session_state[key] = saved_value
    warning_key = f"{key}_browse_warning"

    def _on_browse() -> None:
        path = _ask_directory()
        if path:
            st.session_state[key] = path
            set_setting(f"path_{key}", path)
            st.session_state.pop(warning_key, None)
        else:
            st.session_state[warning_key] = True

    col1, col2 = st.columns([5, 1])
    with col1:
        value = st.text_input(label, key=key, help=help_text)
        if st.session_state.get(warning_key):
            st.warning("無法開啟資料夾選擇器，請手動輸入路徑。")
    with col2:
        st.write("")
        st.button("📁", key=f"{key}_browse", on_click=_on_browse, help="選擇資料夾")

    if value != saved_value:
        set_setting(f"path_{key}", value)

    return value


def validate_path(path: str, label: str, must_exist: bool = True) -> bool:
    if not path or not path.strip():
        st.error(f"請輸入{label}")
        return False
    if must_exist and not os.path.isdir(path):
        st.error(f"{label}不存在：{path}")
        return False
    return True


# =============================================================================
# 顯示元件
# =============================================================================


def ops_to_table(rows: list[dict[str, Any]], height: int = 300) -> None:
    if rows:
        st.dataframe(rows, use_container_width=True, height=height)
    else:
        st.info("（無資料）")


def show_metrics(metrics: list[tuple[str, Any, str | None]]) -> None:
    cols = st.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        with col:
            st.metric(label=label, value=value, delta=delta)


def confirm_checkbox(label: str, key: str) -> bool:
    st.warning("⚠️ 請確認後再執行")
    return st.checkbox(label, value=False, key=key)


def show_success_message(message: str) -> None:
    st.balloons()
    st.success(message)
    st.toast(message, icon="✅")


def download_csv_button(label: str, csv_text: str, filename: str, key: str) -> None:
    # utf-8-sig 讓 Excel 正確顯示中文
    st.download_button(
        label,
        csv_text.encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def show_failures(failures: list[dict[str, Any]]) -> None:
    if failures:
        st.error(f"❌ {len(failures)} 個檔案處理失敗（其餘已完成）")
        ops_to_table(failures, height=200)


def show_undo_hint(log_path: str) -> None:
    st.info(f"↩️ 如需復原，切換到「復原操作」頁籤選擇此 log：`{log_path}`")


def show_image_preview(file_path: str) -> None:
    ext = os.path.splitext(file_path)[1].lower()
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    if ext in image_exts and os.path.exists(file_path):
        try:
            st.image(file_path, width=200, caption=os.path.basename(file_path))
        except Exception:
            pass


# =============================================================================
# 設定區塊（共用）
# =============================================================================


def clean_settings_ui(key_prefix: str) -> tuple[bool, bool, bool, bool, int]:
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
    return (
        clean_names,
        clean_copy_suffix,
        clean_normalize_space,
        clean_remove_special,
        int(conflict_width),
    )


def dupe_settings_ui(key_prefix: str) -> tuple[str, str, int, str]:
    with st.expander("🔍 重複檔案偵測設定", expanded=False):
        dupe_strategy = select_with_mapping(
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
            prefer_path = path_input(
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
            full_hash = select_with_mapping(
                "完整 hash 演算法",
                [("SHA256（安全）", "sha256"), ("xxhash64（快速）", "xxhash64")],
                index=0,
                key=f"{key_prefix}_full_hash",
            )
    return dupe_strategy, prefer_path, int(partial_size_mb), full_hash


def filter_settings_ui(key_prefix: str) -> tuple[int, bool, set[str] | None]:
    """掃描過濾設定，回傳 (min_size_bytes, include_hidden, exclude_dirs)。"""
    with st.expander("🧯 掃描過濾", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            min_size_kb = st.number_input(
                "最小檔案大小（KB，0 = 不過濾）",
                min_value=0,
                value=0,
                key=f"{key_prefix}_min_size",
            )
        with col2:
            skip_hidden = st.checkbox(
                "略過隱藏檔案（. 開頭）",
                value=True,
                key=f"{key_prefix}_skip_hidden",
            )
        exclude_text = st.text_input(
            "排除資料夾名稱（逗號分隔）",
            value=DEFAULT_EXCLUDE_DIRS,
            key=f"{key_prefix}_exclude_dirs",
        )
    exclude_dirs = {d.strip() for d in exclude_text.split(",") if d.strip()} or None
    return int(min_size_kb) * 1024, not skip_hidden, exclude_dirs


def parse_exts_text(value: str, defaults: set[str]) -> set[str]:
    items = {v.strip().lower() for v in value.split(",") if v.strip()}
    if not items:
        return defaults
    normalized = set()
    for ext in items:
        normalized.add(ext if ext.startswith(".") else f".{ext}")
    return normalized
