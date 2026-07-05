"""模式：相似照片偵測（perceptual hash）。"""
from __future__ import annotations

import csv
import io
import os
import shutil

import streamlit as st

from core import (
    DestinationResolver,
    default_log_path,
    find_similar_images,
    iter_files,
    make_record,
    write_oplog,
)
from core.similar import SIMILAR_IMAGE_EXTS

from .common import (
    ProgressBar,
    add_history,
    clear_results,
    clear_results_button,
    confirm_checkbox,
    download_csv_button,
    filter_settings_ui,
    get_results,
    init_results_state,
    path_input,
    set_results,
    show_failures,
    show_image_preview,
    show_metrics,
    show_success_message,
    show_undo_hint,
    validate_path,
)


def _groups_csv(groups) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["group", "path", "phash", "distance_to_first"])
    for idx, group in enumerate(groups, start=1):
        for item in group:
            writer.writerow([idx, item.path, item.phash, item.distance])
    return buf.getvalue()


def similar_photos_ui() -> None:
    st.header("🪞 相似照片偵測")

    init_results_state("similar")

    with st.expander("📖 使用說明", expanded=False):
        st.markdown("""
用 perceptual hash 找出「內容近似但不完全相同」的照片：
不同解析度的輸出、輕度調色、重新壓縮的副本等。

1. 選擇掃描資料夾，調整相似度門檻
2. 按「一鍵預覽」查看相似群組（每組第一張為代表）
3. 可選擇把每組除代表外的照片移到輸出資料夾，執行後可在「復原操作」還原

**注意**：
- 完全相同的檔案請改用「單資料夾去重」（byte 級比對更快更準）
- 門檻越大越寬鬆，誤判也越多；建議從預設值開始
- O(n²) 比對，建議數千張以內
        """)

    st.subheader("📂 資料夾設定")
    source = path_input("掃描資料夾", "similar_source", ".")
    output_folder = path_input("輸出資料夾（存放移出的相似照片）", "similar_output", "similar_output")

    col1, col2 = st.columns(2)
    with col1:
        recursive = st.checkbox("🔄 遞迴掃描子資料夾", value=True, key="similar_recursive")
    with col2:
        max_distance = st.slider(
            "相似度門檻（Hamming distance）",
            min_value=0,
            max_value=16,
            value=5,
            help="0 = 幾乎相同；越大越寬鬆",
        )

    min_size, include_hidden, exclude_dirs = filter_settings_ui("similar")

    st.divider()

    confirm = confirm_checkbox("我了解這將移動檔案（每組保留第一張）", "similar_confirm")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        preview_clicked = st.button("👁️ 一鍵預覽", key="similar_preview", use_container_width=True)
    with col2:
        execute_clicked = st.button(
            "▶️ 移出相似照片",
            disabled=not confirm,
            key="similar_execute",
            use_container_width=True,
            type="primary",
        )
    with col3:
        clear_results_button("similar")

    def _validate() -> bool:
        if not validate_path(source, "掃描資料夾"):
            return False
        if not validate_path(output_folder, "輸出資料夾", must_exist=False):
            return False
        return True

    def _scan(progress: ProgressBar):
        progress.set(0.05, "收集圖片清單...")
        paths = []
        for path in iter_files(source, recursive, include_hidden, exclude_dirs):
            if os.path.splitext(path)[1].lower() not in SIMILAR_IMAGE_EXTS:
                continue
            try:
                if min_size and os.path.getsize(path) < min_size:
                    continue
            except OSError:
                continue
            paths.append(path)
        groups = find_similar_images(
            paths,
            max_distance=max_distance,
            progress=progress.stage("計算 perceptual hash", 0.1, 0.9),
        )
        return paths, groups

    if preview_clicked:
        if not _validate():
            return

        progress = ProgressBar()
        paths, groups = _scan(progress)
        progress.done()

        set_results("similar", {
            "total": len(paths),
            "groups": groups,
        })

        add_history("相似照片偵測", "preview", {"count": len(groups)})

    results = get_results("similar")
    if results:
        groups = results["groups"]
        to_move = sum(len(g) - 1 for g in groups)
        st.success("預覽完成！")
        show_metrics([
            ("掃描圖片", results["total"], None),
            ("相似群組", len(groups), None),
            ("將移出", to_move, None),
        ])

        if groups:
            download_csv_button(
                "⬇️ 下載相似群組 CSV",
                _groups_csv(groups),
                "similar_groups.csv",
                "similar_dl_report",
            )

            for idx, group in enumerate(groups[:20], start=1):
                with st.expander(
                    f"群組 {idx}（{len(group)} 張，保留第一張）", expanded=idx <= 3
                ):
                    cols = st.columns(min(4, len(group)))
                    for i, item in enumerate(group[:4]):
                        with cols[i]:
                            show_image_preview(item.path)
                            label = "✅ 保留" if i == 0 else f"距離 {item.distance}"
                            st.caption(f"{label}\n\n`{item.path}`")
            if len(groups) > 20:
                st.caption(f"（僅顯示前 20 組，完整清單請下載 CSV，共 {len(groups)} 組）")
        else:
            st.info("沒有找到相似照片")

    if execute_clicked:
        if not _validate():
            return
        if not results or not results["groups"]:
            st.error("請先執行預覽")
            return

        groups = results["groups"]
        progress = ProgressBar()
        move_cb = progress.stage("移出相似照片", 0.1, 0.95)

        resolver = DestinationResolver()
        records = []
        moved = 0
        failures = []
        total = sum(len(g) - 1 for g in groups)
        done = 0
        os.makedirs(output_folder, exist_ok=True)

        for group in groups:
            for item in group[1:]:  # 保留第一張
                done += 1
                move_cb(done, total)
                _, dest, _ = resolver.resolve(
                    output_folder, os.path.basename(item.path), 3
                )
                try:
                    shutil.move(item.path, dest)
                    moved += 1
                    records.append(
                        make_record("move", item.path, dest, "moved", "similar")
                    )
                except Exception as exc:  # noqa: BLE001
                    failures.append({"source": item.path, "error": str(exc)})
                    records.append(
                        make_record("move", item.path, dest, "failed", "similar", error=str(exc))
                    )

        log_path = default_log_path(output_folder)
        write_oplog(records, log_path)

        progress.done()

        add_history("相似照片偵測", "execute", {"count": moved}, log_path=log_path)
        clear_results("similar")
        show_success_message(f"✅ 已移出 {moved} 張相似照片（每組保留第一張）")
        show_failures(failures)
        show_undo_hint(log_path)
