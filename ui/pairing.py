"""模式：RAW/JPG 配對。"""
from __future__ import annotations

import os

import streamlit as st

from core import (
    JPG_EXTS_DEFAULT,
    RAW_EXTS_DEFAULT,
    default_log_path,
    execute_pair_actions,
    orphans_report_csv,
    pair_actions_to_records,
    pair_by_stem,
    pairs_report_csv,
    plan_pair_layout,
    write_oplog,
    write_pairs_report,
)

from .common import (
    ProgressBar,
    add_history,
    clear_results,
    clear_results_button,
    confirm_checkbox,
    download_csv_button,
    get_results,
    init_results_state,
    ops_to_table,
    parse_exts_text,
    path_input,
    select_with_mapping,
    set_results,
    show_failures,
    show_file_estimate,
    show_image_preview,
    show_metrics,
    show_success_message,
    show_undo_hint,
    validate_path,
)


def pairing_ui() -> None:
    st.header("📷 RAW/JPG 配對工具")

    init_results_state("pair")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
1. 選擇 JPG 與 RAW 資料夾，並設定輸出資料夾
2. 選擇模式：只複製 RAW 或成對整理
3. 建議先按「一鍵預覽」，確認 pairs / orphans 清單（預覽不會動到任何檔案）
4. 勾選確認後再執行；執行後可在「復原操作」還原
        """)

    st.subheader("📂 資料夾設定")
    col1, col2 = st.columns(2)
    with col1:
        jpg_folder = path_input("JPG 資料夾", "pair_jpg", "folder1")
    with col2:
        raw_folder = path_input("RAW 資料夾", "pair_raw", "folder2")
    output_folder = path_input("輸出資料夾", "pair_output", "pair_output")

    st.subheader("⚙️ 配對設定")
    col1, col2 = st.columns(2)
    with col1:
        mode = select_with_mapping(
            "模式",
            [("只複製 RAW", "copy-raw"), ("成對整理", "pair-organize")],
            index=0,
        )
    with col2:
        key_mode = select_with_mapping(
            "配對 key",
            [("檔名（stem）", "stem"), ("檔名 + 父資料夾", "stem+parent")],
            index=0,
        )

    recursive = st.checkbox("🔄 遞迴掃描子資料夾", value=False)

    if os.path.isdir(jpg_folder) or os.path.isdir(raw_folder):
        show_file_estimate([(jpg_folder, recursive), (raw_folder, recursive)])

    with st.expander("📝 副檔名設定", expanded=False):
        jpg_exts_text = st.text_input(
            "JPG 副檔名（逗號分隔）",
            value=",".join(sorted(JPG_EXTS_DEFAULT)),
        )
        raw_exts_text = st.text_input(
            "RAW 副檔名（逗號分隔）",
            value=",".join(sorted(RAW_EXTS_DEFAULT)),
        )

    with st.expander("📁 成對整理布局（pair-organize 模式）", expanded=False):
        layout = select_with_mapping(
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

    confirm = confirm_checkbox("我了解這將複製/移動檔案", "pair_confirm")

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
        clear_results_button("pair")

    def _validate() -> bool:
        if not validate_path(jpg_folder, "JPG 資料夾") or not validate_path(raw_folder, "RAW 資料夾"):
            return False
        if not validate_path(output_folder, "輸出資料夾", must_exist=False):
            return False
        return True

    def _pair(progress: ProgressBar):
        jpg_exts = parse_exts_text(jpg_exts_text, JPG_EXTS_DEFAULT)
        raw_exts = parse_exts_text(raw_exts_text, RAW_EXTS_DEFAULT)
        progress.set(0.2, "掃描與配對...")
        return pair_by_stem(
            jpg_folder,
            raw_folder,
            recursive=recursive,
            jpg_exts=jpg_exts,
            raw_exts=raw_exts,
            key_mode=key_mode,
        )

    if preview_clicked:
        if not _validate():
            return

        progress = ProgressBar()
        pairs, orphan_jpgs, orphan_raws = _pair(progress)
        progress.done()

        pair_rows = [{"key": p.key, "JPG": p.jpg_path, "RAW": p.raw_path} for p in pairs]
        orphan_rows = (
            [{"類型": "JPG", "路徑": p} for p in orphan_jpgs]
            + [{"類型": "RAW", "路徑": p} for p in orphan_raws]
        )

        set_results("pair", {
            "pairs": pairs,
            "orphan_jpgs": orphan_jpgs,
            "orphan_raws": orphan_raws,
            "pair_rows": pair_rows,
            "orphan_rows": orphan_rows,
        })

        add_history("RAW/JPG 配對", "preview", {"count": len(pairs)})

    results = get_results("pair")
    if results:
        st.success("預覽完成！執行時會直接使用此配對清單。")
        show_metrics([
            ("配對成功", len(results["pairs"]), None),
            ("孤兒 JPG", len(results["orphan_jpgs"]), "⚠️" if results["orphan_jpgs"] else None),
            ("孤兒 RAW", len(results["orphan_raws"]), "⚠️" if results["orphan_raws"] else None),
        ])

        col1, col2 = st.columns(2)
        with col1:
            download_csv_button(
                "⬇️ 下載配對報表 CSV",
                pairs_report_csv(results["pairs"]),
                "pairs.csv",
                "pair_dl_pairs",
            )
        with col2:
            download_csv_button(
                "⬇️ 下載孤兒報表 CSV",
                orphans_report_csv(results["orphan_jpgs"], results["orphan_raws"]),
                "orphans.csv",
                "pair_dl_orphans",
            )

        if results["pairs"]:
            with st.expander("🖼️ 圖片預覽", expanded=False):
                preview_cols = st.columns(min(4, len(results["pairs"])))
                for i, p in enumerate(results["pairs"][:4]):
                    with preview_cols[i]:
                        show_image_preview(p.jpg_path)

        with st.expander("📋 Pairs 清單", expanded=True):
            ops_to_table(results["pair_rows"])
        with st.expander("📋 Orphans 清單", expanded=len(results["orphan_rows"]) > 0):
            ops_to_table(results["orphan_rows"])

    if execute_clicked:
        if not _validate():
            return

        progress = ProgressBar()

        if results:
            pairs = results["pairs"]
            orphan_jpgs = results["orphan_jpgs"]
            orphan_raws = results["orphan_raws"]
            progress.set(0.3, "使用預覽清單...")
        else:
            pairs, orphan_jpgs, orphan_raws = _pair(progress)

        os.makedirs(output_folder, exist_ok=True)
        report_pairs = os.path.join(output_folder, "pairs.csv")
        report_orphans = os.path.join(output_folder, "orphans.csv")
        write_pairs_report(pairs, orphan_jpgs, orphan_raws, report_pairs, report_orphans)

        if mode == "copy-raw":
            actions = plan_pair_layout(
                pairs, output_folder, layout="raw-with-jpg", action="copy", conflict_suffix_width=3
            )
            actions = [a for a in actions if a.role == "raw"]
            effective_move = False
            verb = "RAW 複製"
        else:
            actions = plan_pair_layout(
                pairs,
                output_folder,
                layout=layout,
                action="move" if use_move else "copy",
                conflict_suffix_width=3,
            )
            effective_move = use_move
            verb = "成對整理"

        copied, completed = execute_pair_actions(
            actions,
            dry_run=False,
            move=effective_move,
            progress=progress.stage("執行配對", 0.4, 0.95),
        )

        failures = [
            {"source": a.src_path, "error": a.error}
            for a in completed
            if a.action == "failed"
        ]

        log_path = default_log_path(output_folder)
        write_oplog(pair_actions_to_records(completed, move=effective_move), log_path)

        progress.done()

        add_history("RAW/JPG 配對", "execute", {"count": copied}, log_path=log_path)
        clear_results("pair")
        show_success_message(f"✅ 完成{verb}：{copied} 個")
        show_failures(failures)
        show_undo_hint(log_path)
