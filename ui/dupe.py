"""模式：重複檔案偵測（兩資料夾比對）。"""
from __future__ import annotations

import os

import streamlit as st

from core import (
    check_overlapping,
    default_log_path,
    duplicate_actions_to_records,
    duplicates_report_csv,
    find_duplicates_between,
    move_duplicates,
    scan_folder,
    write_duplicates_report,
    write_oplog,
)

from .common import (
    ProgressBar,
    add_history,
    clean_settings_ui,
    clear_results,
    clear_results_button,
    confirm_checkbox,
    download_csv_button,
    filter_settings_ui,
    get_results,
    init_results_state,
    ops_to_table,
    path_input,
    select_with_mapping,
    set_results,
    show_failures,
    show_file_estimate,
    show_metrics,
    show_success_message,
    show_undo_hint,
    validate_path,
)


def duplicate_finder_ui() -> None:
    st.header("🔍 重複檔案偵測")

    init_results_state("dupe")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
1. 選擇「資料夾 1 / 資料夾 2」與輸出資料夾
2. 建議先按「一鍵預覽」確認移動清單與衝突清單
3. 若要實際移動，勾選確認後再按「執行移動」
4. 執行後會輸出報表與操作 log，可隨時在「復原操作」還原
        """)

    with st.expander("❓ 常見問題", expanded=False):
        st.markdown("""
- **資料夾重疊**：兩資料夾相同會直接擋下；互為子資料夾需勾選確認
- **優先保留指定資料夾**：重複檔案中，指定資料夾內的檔案會優先被保留
- **命名衝突**：若輸出資料夾已有同名檔案，會自動加上 `_001`
- **資源回收桶**：勾選後重複檔改送資源回收桶（無法自動復原）
        """)

    # 路徑輸入
    st.subheader("📂 資料夾設定")
    col1, col2 = st.columns(2)
    with col1:
        folder1 = path_input("資料夾 1", "dupe_folder1", "folder1")
    with col2:
        folder2 = path_input("資料夾 2", "dupe_folder2", "folder2")
    output_folder = path_input("輸出資料夾", "dupe_output", "output_folder")

    recursive = st.checkbox("🔄 遞迴掃描子資料夾", value=False)

    if os.path.isdir(folder1) or os.path.isdir(folder2):
        show_file_estimate([(folder1, recursive), (folder2, recursive)])

    # 比對設定
    with st.expander("⚙️ 比對設定", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            partial_size_mb = st.number_input(
                "partial hash 大小（MB）", min_value=1, value=1
            )
        with col2:
            full_hash = select_with_mapping(
                "完整 hash 演算法",
                [("SHA256（安全）", "sha256"), ("xxhash64（快速）", "xxhash64")],
                index=0,
            )

    # 保留策略
    with st.expander("🎯 保留策略", expanded=False):
        keep_strategy = select_with_mapping(
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
            prefer_path = path_input(
                "優先保留的資料夾",
                "dupe_prefer_path",
                "",
                help_text="重複檔案中，此資料夾內的檔案會優先被保留",
            )

        move_scope = select_with_mapping(
            "移動範圍",
            [("只移動資料夾 2", "folder2"), ("兩邊都可移動", "both")],
            index=0,
        )
        to_trash = st.checkbox(
            "🗑️ 移到資源回收桶（取代移到輸出資料夾）",
            value=False,
            key="dupe_to_trash",
        )

    min_size, include_hidden, exclude_dirs = filter_settings_ui("dupe")

    clean_names, clean_copy_suffix, clean_normalize_space, clean_remove_special, conflict_width = clean_settings_ui("dupe")

    st.divider()

    confirm = confirm_checkbox("我了解這將移動檔案", "dupe_confirm")

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
        clear_results_button("dupe")

    def _validate() -> bool:
        if keep_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return False
        if not validate_path(folder1, "資料夾 1") or not validate_path(folder2, "資料夾 2"):
            return False
        if not to_trash and not validate_path(output_folder, "輸出資料夾", must_exist=False):
            return False

        overlap = check_overlapping(folder1, folder2)
        if overlap == "same":
            st.error("❌ 資料夾 1 與資料夾 2 是同一個資料夾。這會把每一組重複檔的兩份都移走，一份都不留，已擋下。")
            return False
        if overlap is not None:
            st.warning("⚠️ 兩個資料夾互為子資料夾，結果可能不符預期。")
            if not st.session_state.get("dupe_overlap_ok"):
                st.checkbox("我了解風險，仍要繼續", key="dupe_overlap_ok")
                return False
        return True

    def _scan_and_match(progress: ProgressBar):
        scan_kwargs = dict(
            min_size=min_size,
            include_hidden=include_hidden,
            exclude_dirs=exclude_dirs,
        )
        progress.set(0.05, "掃描資料夾 1...")
        files1 = scan_folder(folder1, recursive, **scan_kwargs)
        progress.set(0.15, "掃描資料夾 2...")
        files2 = scan_folder(folder2, recursive, **scan_kwargs)
        matches = find_duplicates_between(
            files1,
            files2,
            partial_bytes=int(partial_size_mb) * 1024 * 1024,
            full_hash_algo=full_hash,
            progress=progress.stage("比對檔案", 0.15, 0.8),
        )
        return files1, files2, matches

    move_kwargs = dict(
        keep_strategy=keep_strategy,
        prefer_path=prefer_path if prefer_path else None,
        move_scope=move_scope,
        to_trash=to_trash,
    )

    def _clean_kwargs() -> dict:
        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )
        return dict(
            clean_names=clean_enabled,
            clean_copy_suffix=clean_copy_suffix or clean_names,
            clean_normalize_space=clean_normalize_space or clean_names,
            clean_remove_special=clean_remove_special or clean_names,
            conflict_suffix_width=conflict_width if clean_enabled else 1,
        )

    # 預覽邏輯
    if preview_clicked:
        if not _validate():
            return

        progress = ProgressBar()
        _, _, matches = _scan_and_match(progress)
        progress.set(0.85, "規劃移動...")

        _, operations = move_duplicates(
            matches,
            output_folder,
            dry_run=True,
            **move_kwargs,
            **_clean_kwargs(),
        )
        progress.done()

        keep_rows = []
        move_rows = []
        conflict_rows = []
        for op in operations:
            if op.action == "kept_by_strategy":
                keep_rows.append({"keep_path": op.keep_path, "strategy": op.strategy})
                continue
            source = op.duplicate.path if op.keep_path != op.duplicate.path else op.original.path
            dest = op.move_path or ("(資源回收桶)" if to_trash else "")
            move_rows.append({"source": source, "dest": dest})
            if op.name_conflict and op.desired_move_path:
                conflict_rows.append(
                    {"source": source, "desired": op.desired_move_path, "final": op.move_path}
                )

        set_results("dupe", {
            "matches": matches,
            "operations": operations,
            "keep_rows": keep_rows,
            "move_rows": move_rows,
            "conflict_rows": conflict_rows,
        })

        add_history("重複檔案偵測", "preview", {"count": len(matches)})

    # 顯示結果
    results = get_results("dupe")
    if results:
        st.success("預覽完成！執行時會直接使用此預覽清單。")
        show_metrics([
            ("重複檔案", len(results["matches"]), None),
            ("保留", len(results["keep_rows"]), None),
            ("將移動", len(results["move_rows"]), None),
            ("命名衝突", len(results["conflict_rows"]), "⚠️" if results["conflict_rows"] else None),
        ])

        download_csv_button(
            "⬇️ 下載重複檔案報表 CSV",
            duplicates_report_csv(results["matches"], results["operations"]),
            "duplicates_report.csv",
            "dupe_dl_report",
        )

        with st.expander("📋 保留清單", expanded=False):
            ops_to_table(results["keep_rows"])
        with st.expander("📋 移動清單", expanded=True):
            ops_to_table(results["move_rows"])
        with st.expander("⚠️ 衝突清單", expanded=len(results["conflict_rows"]) > 0):
            ops_to_table(results["conflict_rows"])

    # 執行邏輯
    if execute_clicked:
        if not _validate():
            return

        progress = ProgressBar()

        # 有預覽結果就直接用，確保「所見即所得」
        if results:
            matches = results["matches"]
            progress.set(0.3, "使用預覽清單...")
        else:
            _, _, matches = _scan_and_match(progress)

        moved_count, operations = move_duplicates(
            matches,
            output_folder,
            dry_run=False,
            progress=progress.stage("處理重複檔案", 0.8, 0.95),
            **move_kwargs,
            **_clean_kwargs(),
        )

        failures = [
            {"source": op.duplicate.path, "error": op.error}
            for op in operations
            if op.action == "failed"
        ]

        log_path = None
        report_path = None
        if not to_trash or moved_count or failures:
            os.makedirs(output_folder, exist_ok=True)
            report_path = os.path.join(output_folder, "duplicates_report.csv")
            write_duplicates_report(matches, report_path, actions=operations)

            log_path = default_log_path(output_folder)
            write_oplog(duplicate_actions_to_records(operations), log_path)

        progress.done()

        add_history("重複檔案偵測", "execute", {"count": moved_count}, log_path=log_path)
        clear_results("dupe")
        verb = "移到資源回收桶" if to_trash else "移動"
        show_success_message(f"✅ 已{verb} {moved_count} 個檔案")
        show_failures(failures)
        if report_path:
            st.caption(f"報表：`{report_path}`")
        if log_path and not to_trash:
            show_undo_hint(log_path)
