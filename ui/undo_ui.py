"""模式：復原操作（從 actions log 還原）。"""
from __future__ import annotations

import os

import streamlit as st

from core import execute_undo, plan_undo, read_oplog

from .common import (
    ProgressBar,
    add_history,
    clear_results,
    clear_results_button,
    confirm_checkbox,
    get_results,
    init_results_state,
    known_undo_logs,
    ops_to_table,
    set_results,
    show_metrics,
    show_success_message,
)

_STATUS_LABELS = {
    "preview": "可還原",
    "restored": "已還原",
    "removed_copy": "已刪除副本",
    "skipped": "略過",
    "failed": "失敗",
}


def _to_rows(actions) -> list[dict]:
    return [
        {
            "狀態": _STATUS_LABELS.get(a.status, a.status),
            "操作": a.op,
            "還原自": a.dest or "",
            "還原到": a.source,
            "說明": a.reason or "",
        }
        for a in actions
    ]


def undo_ui() -> None:
    st.header("↩️ 復原操作")

    init_results_state("undo")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
每次執行都會在輸出資料夾產生 `actions_log_*.jsonl`，這裡可以反向還原：

- **移動**：把檔案從目的地搬回原始位置
- **複製**：刪除複製出來的副本（原始檔不受影響）
- **資源回收桶**：無法自動還原，請手動從回收桶還原

還原按「後進先出」順序執行；如果原始位置已被佔用會略過該筆。
        """)

    st.subheader("📄 選擇操作 log")

    logs = known_undo_logs()
    log_path = ""
    if logs:
        options = ["（手動輸入路徑）"] + logs
        choice = st.selectbox("最近的操作 log", options, index=1 if logs else 0)
        if choice != "（手動輸入路徑）":
            log_path = choice
    if not log_path:
        log_path = st.text_input("log 檔路徑", value="", key="undo_log_path")

    st.divider()

    confirm = confirm_checkbox("我了解這將移動/刪除檔案以還原先前操作", "undo_confirm")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        preview_clicked = st.button("👁️ 預覽還原", key="undo_preview", use_container_width=True)
    with col2:
        execute_clicked = st.button(
            "▶️ 執行還原",
            disabled=not confirm,
            key="undo_execute",
            use_container_width=True,
            type="primary",
        )
    with col3:
        clear_results_button("undo")

    def _validate() -> bool:
        if not log_path or not os.path.isfile(log_path):
            st.error(f"log 檔不存在：{log_path}")
            return False
        return True

    if preview_clicked:
        if not _validate():
            return

        records = read_oplog(log_path)
        actions = plan_undo(records)
        results_list = execute_undo(actions, dry_run=True)

        set_results("undo", {
            "log_path": log_path,
            "records": len(records),
            "preview": results_list,
        })

    results = get_results("undo")
    if results:
        preview = results["preview"]
        restorable = sum(1 for a in preview if a.status == "preview")
        skipped = sum(1 for a in preview if a.status == "skipped")
        st.success(f"log：`{results['log_path']}`（{results['records']} 筆記錄）")
        show_metrics([
            ("可還原", restorable, None),
            ("略過", skipped, "⚠️" if skipped else None),
        ])
        with st.expander("📋 還原清單", expanded=True):
            ops_to_table(_to_rows(preview), height=400)

    if execute_clicked:
        if not _validate():
            return

        progress = ProgressBar()
        records = read_oplog(log_path)
        actions = plan_undo(records)
        completed = execute_undo(
            actions, dry_run=False, progress=progress.stage("還原中", 0.05, 0.95)
        )
        progress.done()

        restored = sum(1 for a in completed if a.status in {"restored", "removed_copy"})
        skipped = sum(1 for a in completed if a.status == "skipped")
        failed = sum(1 for a in completed if a.status == "failed")

        add_history("復原操作", "undo", {"count": restored})
        clear_results("undo")
        show_success_message(f"✅ 還原完成：{restored} 筆（略過 {skipped}、失敗 {failed}）")
        with st.expander("📋 還原結果", expanded=failed > 0):
            ops_to_table(_to_rows(completed), height=400)
