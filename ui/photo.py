"""模式：攝影素材整理。"""
from __future__ import annotations

import os

import streamlit as st

from core import (
    PairRecord,
    default_log_path,
    duplicates_report_csv,
    execute_duplicate_actions,
    execute_photo_actions,
    orphans_report_csv,
    pairs_report_csv,
    plan_photo_actions,
    write_actions_log,
    write_duplicates_report,
    write_pairs_report,
)
from rules_presets import PHOTO_PRESET

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


def photo_organizer_ui() -> None:
    st.header("🎞️ 攝影素材整理")

    init_results_state("photo")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
1. 選擇來源與輸出資料夾
2. 選擇配對 key 與輸出布局
3. 可選擇是否啟用重複檔案偵測
4. 建議先按「一鍵預覽」，查看 pairs / orphans / duplicates（預覽不會動到任何檔案）
5. 勾選確認後執行；執行後可在「復原操作」還原

**注意**：EXIF 配對 key 精度只到秒，連拍照片可能錯配，建議連拍素材改用檔名配對。
        """)

    st.subheader("📂 資料夾設定")
    source = path_input("來源資料夾", "photo_source", ".")
    output = path_input("輸出資料夾", "photo_output", "photo_output")

    recursive = st.checkbox("🔄 遞迴掃描子資料夾", value=True)

    if os.path.isdir(source):
        show_file_estimate([(source, recursive)])

    st.subheader("⚙️ 配對與輸出")
    col1, col2 = st.columns(2)
    with col1:
        layout = select_with_mapping(
            "輸出布局",
            [
                ("依日期/類型分類", "by-date-type"),
                ("每張一資料夾", "per-pair-folder"),
            ],
            index=0,
        )
    with col2:
        pair_key = select_with_mapping(
            "配對 key",
            [
                ("檔名（stem）", "stem"),
                ("檔名 + 父資料夾", "stem+parent"),
                ("EXIF 拍攝時間", "exif"),
            ],
            index=0,
        )

    enable_duplicates = st.checkbox("🔍 啟用重複檔案偵測", value=True)

    if enable_duplicates:
        dupe_strategy, prefer_path, partial_size_mb, full_hash = dupe_settings_ui("photo")
    else:
        dupe_strategy, prefer_path, partial_size_mb, full_hash = "latest", "", 1, "sha256"

    min_size, include_hidden, exclude_dirs = filter_settings_ui("photo")

    st.subheader("▶️ 執行設定")
    use_move = st.checkbox("使用移動（Move）而非複製", value=False)

    st.divider()

    confirm = confirm_checkbox("我了解這將移動/複製檔案", "photo_confirm")

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
        clear_results_button("photo")

    def _validate() -> bool:
        if not validate_path(source, "來源資料夾"):
            return False
        if not validate_path(output, "輸出資料夾", must_exist=False):
            return False
        if enable_duplicates and dupe_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入優先保留的資料夾")
            return False
        return True

    def _plan(progress: ProgressBar):
        scan_cb = progress.stage("掃描媒體檔案", 0.05, 0.5)
        hash_cb = progress.stage("比對重複檔案", 0.5, 0.85)

        def stage_progress(stage: str, done: int, total: int) -> None:
            if stage == "scan":
                scan_cb(done, total)
            else:
                hash_cb(done, total)

        return plan_photo_actions(
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
            min_size=min_size,
            include_hidden=include_hidden,
            exclude_dirs=exclude_dirs,
            progress=stage_progress,
        )

    if preview_clicked:
        if not _validate():
            return

        progress = ProgressBar()
        plan = _plan(progress)
        progress.done()

        pair_rows = [{"key": p[0], "JPG": p[1], "RAW": p[2]} for p in plan.pairs]
        orphan_rows = (
            [{"類型": "JPG", "路徑": p} for p in plan.orphan_jpgs]
            + [{"類型": "RAW", "路徑": p} for p in plan.orphan_raws]
        )
        action_rows = [
            {
                "來源": a.source_path,
                "目的地": a.dest_path,
                "分類": a.category,
                "日期": a.shot_date,
                "衝突": "⚠️" if a.name_conflict else "",
            }
            for a in plan.photo_actions
        ]

        set_results("photo", {
            "plan": plan,
            "pair_rows": pair_rows,
            "orphan_rows": orphan_rows,
            "action_rows": action_rows,
        })

        add_history("攝影素材整理", "preview", {"count": len(plan.media_files)})

    results = get_results("photo")
    if results:
        plan = results["plan"]

        st.success("預覽完成！執行時會直接使用此計畫。")
        show_metrics([
            ("來源檔案", len(plan.media_files), None),
            ("配對成功", len(plan.pairs), None),
            ("孤兒 JPG", len(plan.orphan_jpgs), "⚠️" if plan.orphan_jpgs else None),
            ("孤兒 RAW", len(plan.orphan_raws), "⚠️" if plan.orphan_raws else None),
        ])
        show_metrics([
            ("重複檔案", len(plan.duplicate_matches), None),
            ("整理項目", len(plan.photo_actions), None),
        ])

        pair_records = [PairRecord(key=p[0], jpg_path=p[1], raw_path=p[2]) for p in plan.pairs]
        col1, col2, col3 = st.columns(3)
        with col1:
            download_csv_button(
                "⬇️ 配對報表 CSV",
                pairs_report_csv(pair_records),
                "pairs.csv",
                "photo_dl_pairs",
            )
        with col2:
            download_csv_button(
                "⬇️ 孤兒報表 CSV",
                orphans_report_csv(plan.orphan_jpgs, plan.orphan_raws),
                "orphans.csv",
                "photo_dl_orphans",
            )
        with col3:
            if plan.duplicate_matches:
                download_csv_button(
                    "⬇️ 重複報表 CSV",
                    duplicates_report_csv(plan.duplicate_matches, plan.duplicate_actions),
                    "duplicates_report.csv",
                    "photo_dl_dupes",
                )

        jpg_files = [p[1] for p in plan.pairs if p[1]][:4]
        if jpg_files:
            with st.expander("🖼️ 圖片預覽", expanded=False):
                preview_cols = st.columns(min(4, len(jpg_files)))
                for i, jpg_path in enumerate(jpg_files):
                    with preview_cols[i]:
                        show_image_preview(jpg_path)

        with st.expander("📋 整理清單", expanded=True):
            ops_to_table(results["action_rows"], height=400)
        with st.expander("📋 Pairs 清單", expanded=False):
            ops_to_table(results["pair_rows"])
        with st.expander("📋 Orphans 清單", expanded=len(results["orphan_rows"]) > 0):
            ops_to_table(results["orphan_rows"])

    if execute_clicked:
        if not _validate():
            return

        progress = ProgressBar()

        # 有預覽結果就直接執行該計畫，確保「所見即所得」
        if results:
            plan = results["plan"]
            progress.set(0.3, "使用預覽計畫...")
        else:
            plan = _plan(progress)

        os.makedirs(output, exist_ok=True)
        pairs_path = os.path.join(output, "pairs.csv")
        orphans_path = os.path.join(output, "orphans.csv")
        pair_records = [PairRecord(key=p[0], jpg_path=p[1], raw_path=p[2]) for p in plan.pairs]
        write_pairs_report(pair_records, plan.orphan_jpgs, plan.orphan_raws, pairs_path, orphans_path)

        completed_duplicates = execute_duplicate_actions(
            plan.duplicate_actions,
            dry_run=False,
            progress=progress.stage("處理重複檔案", 0.4, 0.6),
        )
        completed_actions = execute_photo_actions(
            plan.photo_actions,
            dry_run=False,
            move=use_move,
            progress=progress.stage("整理檔案", 0.6, 0.95),
        )

        log_path = default_log_path(output)
        write_actions_log(completed_actions, completed_duplicates, log_path)

        if plan.duplicate_matches:
            duplicates_path = os.path.join(output, "duplicates_report.csv")
            write_duplicates_report(plan.duplicate_matches, duplicates_path, completed_duplicates)

        failures = [
            {"source": a.source_path, "error": a.error}
            for a in completed_actions
            if a.action == "failed"
        ] + [
            {"source": a.duplicate.path, "error": a.error}
            for a in completed_duplicates
            if a.action == "failed"
        ]

        progress.done()

        done_count = sum(1 for a in completed_actions if a.action in {"moved", "copied"})
        add_history("攝影素材整理", "execute", {"count": done_count}, log_path=log_path)
        clear_results("photo")
        show_success_message(f"✅ 已完成整理：{done_count} 個檔案")
        show_failures(failures)
        show_undo_hint(log_path)
