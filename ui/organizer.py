"""模式：工作檔案整理。"""
from __future__ import annotations

import os

import streamlit as st

from core import (
    default_log_path,
    duplicate_actions_to_records,
    organize,
    organize_actions_to_records,
    organize_report_csv,
    write_oplog,
)
from rules_presets import WORK_PRESET

from .common import (
    ProgressBar,
    add_history,
    clean_settings_ui,
    clear_results,
    clear_results_button,
    confirm_checkbox,
    download_csv_button,
    dupe_settings_ui,
    filter_settings_ui,
    get_results,
    init_results_state,
    ops_to_table,
    path_input,
    set_results,
    show_failures,
    show_file_estimate,
    show_metrics,
    show_success_message,
    show_undo_hint,
    validate_path,
)


def organizer_ui() -> None:
    st.header("📁 工作檔案整理助手")

    init_results_state("org")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
1. 選擇來源資料夾與輸出資料夾
2. 依需求開啟：遞迴掃描 / 時間分層 / 重複檔案偵測
3. 建議先按「一鍵預覽」確認整理清單（預覽不會動到任何檔案）
4. 勾選確認後再按「執行整理」；執行後可在「復原操作」還原
        """)

    with st.expander("❓ 常見問題", expanded=False):
        st.markdown("""
- **Duplicates/**：重複檔案會移到輸出資料夾內的 `Duplicates/`
- **時間分層**：會依檔案修改時間分到 `/YYYY-MM/分類`
- **命名衝突**：若目的地已有同名檔案，會自動加上 `_001`
- **執行 vs 預覽**：執行時會重新掃描來源（期間有變動會以執行當下為準）
        """)

    st.subheader("📂 資料夾設定")
    source = path_input("來源資料夾", "org_source", ".")
    output = path_input("輸出資料夾", "org_output", "organized_output")

    col1, col2, col3 = st.columns(3)
    with col1:
        recursive = st.checkbox("🔄 遞迴掃描", value=True)
    with col2:
        time_partition = st.checkbox("📅 時間分層", value=False)
    with col3:
        enable_duplicates = st.checkbox("🔍 偵測重複", value=True)

    if os.path.isdir(source):
        show_file_estimate([(source, recursive)])

    skip_duplicates = not enable_duplicates

    if enable_duplicates:
        dupe_strategy, prefer_path, partial_size_mb, full_hash = dupe_settings_ui("org")
    else:
        dupe_strategy, prefer_path, partial_size_mb, full_hash = "latest", "", 1, "sha256"

    min_size, include_hidden, exclude_dirs = filter_settings_ui("org")

    clean_names, clean_copy_suffix, clean_normalize_space, clean_remove_special, conflict_width = clean_settings_ui("org")

    st.divider()

    confirm = confirm_checkbox("我了解這將移動檔案", "org_confirm")

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
        clear_results_button("org")

    def _validate() -> bool:
        if enable_duplicates and dupe_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return False
        if not validate_path(source, "來源資料夾"):
            return False
        if not validate_path(output, "輸出資料夾", must_exist=False):
            return False
        return True

    def _run(dry_run: bool, progress: ProgressBar):
        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )

        hash_cb = progress.stage("比對重複檔案", 0.1, 0.6)
        move_cb = progress.stage("規劃整理" if dry_run else "整理檔案", 0.6, 0.95)

        def stage_progress(stage: str, done: int, total: int) -> None:
            if stage == "hash":
                hash_cb(done, total)
            else:
                move_cb(done, total)

        progress.set(0.05, "掃描檔案...")
        return organize(
            source_folder=source,
            output_folder=output,
            recursive=recursive,
            time_partition=time_partition,
            dry_run=dry_run,
            skip_duplicates=skip_duplicates,
            dupe_strategy=dupe_strategy,
            prefer_path=prefer_path if prefer_path else None,
            partial_size_mb=partial_size_mb,
            full_hash_algo=full_hash,
            clean_names=clean_enabled,
            clean_copy_suffix=clean_copy_suffix or clean_names,
            clean_normalize_space=clean_normalize_space or clean_names,
            clean_remove_special=clean_remove_special or clean_names,
            conflict_suffix_width=conflict_width if clean_enabled else 1,
            preset=WORK_PRESET,
            min_size=min_size,
            include_hidden=include_hidden,
            exclude_dirs=exclude_dirs,
            progress=stage_progress,
        )

    if preview_clicked:
        if not _validate():
            return

        progress = ProgressBar()
        total_files, duplicate_matches, duplicate_actions, organize_actions = _run(
            dry_run=True, progress=progress
        )
        progress.done()

        org_rows = [
            {
                "來源": a.source_path,
                "目的地": a.dest_path,
                "分類": a.category,
                "衝突": "⚠️" if a.name_conflict else "",
            }
            for a in organize_actions
        ]

        set_results("org", {
            "total_files": total_files,
            "duplicate_matches": duplicate_matches,
            "organize_actions": organize_actions,
            "org_rows": org_rows,
        })

        add_history("工作檔案整理", "preview", {"count": total_files})

    results = get_results("org")
    if results:
        st.success("預覽完成！（預覽不會動到任何檔案）")
        show_metrics([
            ("來源檔案", results["total_files"], None),
            ("重複檔案", len(results["duplicate_matches"]), None),
            ("整理項目", len(results["organize_actions"]), None),
        ])

        download_csv_button(
            "⬇️ 下載整理清單 CSV",
            organize_report_csv(results["organize_actions"]),
            "organize_report.csv",
            "org_dl_report",
        )

        with st.expander("📋 整理清單", expanded=True):
            ops_to_table(results["org_rows"], height=400)

    if execute_clicked:
        if not _validate():
            return

        progress = ProgressBar()
        total_files, duplicate_matches, duplicate_actions, organize_actions = _run(
            dry_run=False, progress=progress
        )

        failures = [
            {"source": a.source_path, "error": a.error}
            for a in organize_actions
            if a.action == "failed"
        ] + [
            {"source": a.duplicate.path, "error": a.error}
            for a in duplicate_actions
            if a.action == "failed"
        ]

        log_path = default_log_path(output)
        records = organize_actions_to_records(organize_actions) + duplicate_actions_to_records(duplicate_actions)
        write_oplog(records, log_path)

        progress.done()

        moved = sum(1 for a in organize_actions if a.action == "moved")
        add_history("工作檔案整理", "execute", {"count": moved}, log_path=log_path)
        clear_results("org")
        show_success_message(
            f"✅ 整理完成！來源 {total_files} 個，整理 {moved} 個，重複 {len(duplicate_matches)} 個"
        )
        show_failures(failures)
        show_undo_hint(log_path)
