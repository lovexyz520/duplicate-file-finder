"""模式：單資料夾去重（掃描同一個資料夾內的重複檔案）。"""
from __future__ import annotations

import os

import streamlit as st

from core import (
    DuplicateMatch,
    default_log_path,
    duplicate_actions_to_records,
    duplicates_report_csv,
    group_duplicates,
    move_duplicates,
    pick_keep_for_group,
    scan_folder,
    write_duplicates_report,
    write_oplog,
)

from .common import (
    ProgressBar,
    add_history,
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


def _matches_from_groups(groups, strategy: str, prefer_path: str | None) -> list[DuplicateMatch]:
    matches: list[DuplicateMatch] = []
    for group in groups:
        keep = pick_keep_for_group([g.info for g in group], strategy, prefer_path)
        for grouped in group:
            if grouped.info.path == keep.path:
                continue
            matches.append(
                DuplicateMatch(
                    original=keep,
                    duplicate=grouped.info,
                    partial_hash=grouped.partial_hash,
                    full_hash=grouped.full_hash,
                )
            )
    return matches


def single_folder_dedupe_ui() -> None:
    st.header("🧹 單資料夾去重")

    init_results_state("single")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
1. 選擇要掃描的資料夾（通常搭配「遞迴掃描」）
2. 按「一鍵預覽」查看每組重複檔案與保留策略結果
3. 勾選確認後執行：重複檔會移到輸出資料夾（或資源回收桶），每組保留一份
4. 執行後會輸出操作 log，可隨時在「復原操作」還原
        """)

    st.subheader("📂 資料夾設定")
    source = path_input("掃描資料夾", "single_source", ".")
    output_folder = path_input("輸出資料夾（存放移出的重複檔）", "single_output", "duplicates_output")

    recursive = st.checkbox("🔄 遞迴掃描子資料夾", value=True, key="single_recursive")

    if os.path.isdir(source):
        show_file_estimate([(source, recursive)])

    dupe_strategy, prefer_path, partial_size_mb, full_hash = dupe_settings_ui("single")

    to_trash = st.checkbox(
        "🗑️ 移到資源回收桶（取代移到輸出資料夾）",
        value=False,
        key="single_to_trash",
    )

    min_size, include_hidden, exclude_dirs = filter_settings_ui("single")

    st.divider()

    confirm = confirm_checkbox("我了解這將移動檔案", "single_confirm")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        preview_clicked = st.button("👁️ 一鍵預覽", key="single_preview", use_container_width=True)
    with col2:
        execute_clicked = st.button(
            "▶️ 執行去重",
            disabled=not confirm,
            key="single_execute",
            use_container_width=True,
            type="primary",
        )
    with col3:
        clear_results_button("single")

    def _validate() -> bool:
        if dupe_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return False
        if not validate_path(source, "掃描資料夾"):
            return False
        if not to_trash and not validate_path(output_folder, "輸出資料夾", must_exist=False):
            return False
        return True

    def _scan_and_group(progress: ProgressBar):
        progress.set(0.05, "掃描資料夾...")
        files = scan_folder(
            source,
            recursive,
            min_size=min_size,
            include_hidden=include_hidden,
            exclude_dirs=exclude_dirs,
        )
        groups = group_duplicates(
            files,
            partial_bytes=partial_size_mb * 1024 * 1024,
            full_hash_algo=full_hash,
            progress=progress.stage("比對檔案", 0.1, 0.8),
        )
        return files, groups

    if preview_clicked:
        if not _validate():
            return

        progress = ProgressBar()
        files, groups = _scan_and_group(progress)
        matches = _matches_from_groups(groups, dupe_strategy, prefer_path or None)
        progress.done()

        group_rows = []
        for idx, group in enumerate(groups, start=1):
            keep = pick_keep_for_group([g.info for g in group], dupe_strategy, prefer_path or None)
            for grouped in group:
                group_rows.append({
                    "群組": idx,
                    "動作": "保留" if grouped.info.path == keep.path else "移出",
                    "路徑": grouped.info.path,
                    "大小": grouped.info.size,
                })

        set_results("single", {
            "total_files": len(files),
            "groups": groups,
            "matches": matches,
            "group_rows": group_rows,
        })

        add_history("單資料夾去重", "preview", {"count": len(matches)})

    results = get_results("single")
    if results:
        st.success("預覽完成！執行時會直接使用此預覽清單。")
        show_metrics([
            ("掃描檔案", results["total_files"], None),
            ("重複群組", len(results["groups"]), None),
            ("將移出", len(results["matches"]), None),
        ])

        download_csv_button(
            "⬇️ 下載重複檔案報表 CSV",
            duplicates_report_csv(results["matches"]),
            "duplicates_report.csv",
            "single_dl_report",
        )

        with st.expander("📋 重複群組清單", expanded=True):
            ops_to_table(results["group_rows"], height=400)

    if execute_clicked:
        if not _validate():
            return

        progress = ProgressBar()

        if results:
            matches = results["matches"]
            progress.set(0.3, "使用預覽清單...")
        else:
            _, groups = _scan_and_group(progress)
            matches = _matches_from_groups(groups, dupe_strategy, prefer_path or None)

        moved_count, operations = move_duplicates(
            matches,
            output_folder,
            dry_run=False,
            keep_strategy="folder1",  # original 即保留檔
            to_trash=to_trash,
            progress=progress.stage("處理重複檔案", 0.8, 0.95),
        )

        failures = [
            {"source": op.duplicate.path, "error": op.error}
            for op in operations
            if op.action == "failed"
        ]

        log_path = None
        if not to_trash:
            os.makedirs(output_folder, exist_ok=True)
            report_path = os.path.join(output_folder, "duplicates_report.csv")
            write_duplicates_report(matches, report_path, actions=operations)
            log_path = default_log_path(output_folder)
            write_oplog(duplicate_actions_to_records(operations), log_path)

        progress.done()

        add_history("單資料夾去重", "execute", {"count": moved_count}, log_path=log_path)
        clear_results("single")
        verb = "移到資源回收桶" if to_trash else "移出"
        show_success_message(f"✅ 已{verb} {moved_count} 個重複檔案")
        show_failures(failures)
        if log_path:
            show_undo_hint(log_path)
