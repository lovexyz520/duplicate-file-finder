from __future__ import annotations

import os
from typing import Any

import streamlit as st

from core import (
    find_duplicates_between,
    move_duplicates,
    organize,
    scan_folder,
    write_duplicates_report,
)
from rules_presets import WORK_PRESET


def _check_overlapping(folder1: str, folder2: str) -> str | None:
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


def _ops_to_table(rows: list[dict[str, Any]]) -> None:
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.write("（無）")


def duplicate_finder_ui() -> None:
    st.header("重複檔案偵測")
    with st.expander("使用說明", expanded=True):
        st.markdown(
            "\n".join(
                [
                    "1. 填入「資料夾 1 / 資料夾 2」，並設定輸出資料夾。",
                    "2. 建議先按「一鍵預覽」確認移動清單與衝突清單。",
                    "3. 若要實際移動，勾選「我了解這將移動檔案」，再按「執行移動」。",
                    "4. 報表會輸出到輸出資料夾的 `duplicates_report.csv`。",
                ]
            )
        )
    with st.expander("常見問題 / 注意事項", expanded=False):
        st.markdown(
            "\n".join(
                [
                    "- **資料夾重疊**：若兩資料夾互為子資料夾，結果可能不準確。",
                    "- **prefer-path**：只有當實際比對的檔案路徑在 prefer-path 內才會生效。",
                    "- **命名衝突**：若輸出資料夾已有同名檔案，會自動加上 `_001`。",
                    "- **先預覽**：建議先預覽，確認無誤再執行移動。",
                ]
            )
        )
    col1, col2 = st.columns(2)
    with col1:
        folder1 = st.text_input("資料夾 1", value="folder1")
    with col2:
        folder2 = st.text_input("資料夾 2", value="folder2")
    output_folder = st.text_input("輸出資料夾", value="output_folder")
    recursive = st.checkbox("遞迴掃描子資料夾", value=False)

    st.subheader("比對設定")
    partial_size_mb = st.number_input("partial hash 大小（MB）", min_value=1, value=1)
    full_hash = st.selectbox("完整 hash", ["sha256", "xxhash64"], index=0)

    st.subheader("保留策略")
    keep_strategy = st.selectbox(
        "保留策略",
        ["folder1", "folder2", "latest", "earliest", "prefer-path"],
        index=0,
    )
    prefer_path = st.text_input("prefer-path（僅當策略為 prefer-path 時）", value="")
    move_scope = st.selectbox("移動範圍", ["folder2", "both"], index=0)

    st.subheader("檔名清理")
    clean_names = st.checkbox(
        "啟用檔名清理（移除(1)/(2)、空白正規化、移除特殊字元、衝突補 _001）",
        value=False,
    )
    clean_copy_suffix = st.checkbox("移除 (1)/(2)", value=False)
    clean_normalize_space = st.checkbox("空白正規化", value=False)
    clean_remove_special = st.checkbox("移除特殊字元", value=False)
    conflict_width = st.number_input("衝突補碼位數", min_value=0, value=3)

    confirm = st.checkbox("我了解這將移動檔案", value=False)

    if st.button("一鍵預覽"):
        if keep_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入 prefer-path")
            return
        if not os.path.isdir(folder1) or not os.path.isdir(folder2):
            st.error("資料夾不存在")
            return
        overlap = _check_overlapping(folder1, folder2)
        if overlap is not None:
            st.warning(f"資料夾重疊：{overlap}")

        files1 = scan_folder(folder1, recursive)
        files2 = scan_folder(folder2, recursive)
        matches = find_duplicates_between(
            files1,
            files2,
            partial_bytes=int(partial_size_mb) * 1024 * 1024,
            full_hash_algo=full_hash,
        )
        st.write(f"重複檔案數量：{len(matches)}")

        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )
        effective_conflict_width = int(conflict_width) if clean_enabled else 1
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
        report_path = os.path.join(output_folder, "duplicates_report.csv")
        write_duplicates_report(matches, report_path, actions=operations)
        st.write(f"報表輸出：{report_path}")

        keep_rows = []
        move_rows = []
        conflict_rows = []
        for op in operations:
            if op.action == "kept_by_strategy":
                keep_rows.append(
                    {
                        "keep_path": op.keep_path,
                        "strategy": op.strategy,
                    }
                )
                continue
            source = op.duplicate.path if op.keep_path != op.duplicate.path else op.original.path
            move_rows.append({"source": source, "dest": op.move_path})
            if op.name_conflict and op.desired_move_path:
                conflict_rows.append(
                    {
                        "source": source,
                        "desired": op.desired_move_path,
                        "final": op.move_path,
                    }
                )

        st.subheader("保留清單")
        _ops_to_table(keep_rows)
        st.subheader("移動清單")
        _ops_to_table(move_rows)
        st.subheader("衝突清單")
        _ops_to_table(conflict_rows)
        st.write(
            f"摘要：重複 {len(matches)}，保留 {len(keep_rows)}，"
            f"預覽移動 {len(move_rows)}，衝突 {len(conflict_rows)}"
        )

    if st.button("執行移動", disabled=not confirm):
        if keep_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入 prefer-path")
            return
        if not os.path.isdir(folder1) or not os.path.isdir(folder2):
            st.error("資料夾不存在")
            return
        files1 = scan_folder(folder1, recursive)
        files2 = scan_folder(folder2, recursive)
        matches = find_duplicates_between(
            files1,
            files2,
            partial_bytes=int(partial_size_mb) * 1024 * 1024,
            full_hash_algo=full_hash,
        )
        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )
        effective_conflict_width = int(conflict_width) if clean_enabled else 1
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
        report_path = os.path.join(output_folder, "duplicates_report.csv")
        write_duplicates_report(matches, report_path, actions=operations)
        st.success(f"已移動 {moved_count} 個檔案。報表：{report_path}")


def organizer_ui() -> None:
    st.header("工作檔案整理助手")
    with st.expander("使用說明", expanded=True):
        st.markdown(
            "\n".join(
                [
                    "1. 選擇來源資料夾與輸出資料夾。",
                    "2. 可選擇是否遞迴掃描、時間分層、跳過重複偵測。",
                    "3. 建議先按「一鍵預覽」查看整理清單與報表位置。",
                    "4. 若要實際整理，勾選「我了解這將移動檔案」，再按「執行整理」。",
                ]
            )
        )
    with st.expander("常見問題 / 注意事項", expanded=False):
        st.markdown(
            "\n".join(
                [
                    "- **Duplicates/**：重複檔案會移到輸出資料夾內的 `Duplicates/`。",
                    "- **時間分層**：會依檔案修改時間分到 `/YYYY-MM/分類`。",
                    "- **命名衝突**：若目的地已有同名檔案，會自動加上 `_001`。",
                    "- **先預覽**：建議先預覽，確認無誤再執行整理。",
                ]
            )
        )
    source = st.text_input("來源資料夾", value=".")
    output = st.text_input("輸出資料夾", value="organized_output")
    recursive = st.checkbox("遞迴掃描子資料夾", value=True)
    time_partition = st.checkbox("時間分層（/YYYY-MM/分類）", value=False)
    skip_duplicates = st.checkbox("略過重複檔案偵測", value=False)

    st.subheader("重複檔案策略")
    dupe_strategy = st.selectbox("保留策略", ["latest", "earliest", "prefer-path"], index=0)
    prefer_path = st.text_input("prefer-path", value="")
    partial_size_mb = st.number_input("partial hash 大小（MB）", min_value=1, value=1)
    full_hash = st.selectbox("完整 hash", ["sha256", "xxhash64"], index=0, key="org_full_hash")

    st.subheader("檔名清理")
    clean_names = st.checkbox(
        "啟用檔名清理（移除(1)/(2)、空白正規化、移除特殊字元、衝突補 _001）",
        value=False,
        key="org_clean_names",
    )
    clean_copy_suffix = st.checkbox("移除 (1)/(2)", value=False, key="org_clean_copy")
    clean_normalize_space = st.checkbox("空白正規化", value=False, key="org_clean_space")
    clean_remove_special = st.checkbox("移除特殊字元", value=False, key="org_clean_special")
    conflict_width = st.number_input("衝突補碼位數", min_value=0, value=3, key="org_conflict")

    confirm = st.checkbox("我了解這將移動檔案", value=False, key="org_confirm")

    if st.button("一鍵預覽", key="org_preview"):
        if dupe_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入 prefer-path")
            return
        if not os.path.isdir(source):
            st.error("來源資料夾不存在")
            return
        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )
        effective_conflict_width = int(conflict_width) if clean_enabled else 1
        total_files, duplicate_matches, _, organize_actions = organize(
            source_folder=source,
            output_folder=output,
            recursive=recursive,
            time_partition=time_partition,
            dry_run=True,
            skip_duplicates=skip_duplicates,
            dupe_strategy=dupe_strategy,
            prefer_path=prefer_path if prefer_path else None,
            partial_size_mb=int(partial_size_mb),
            full_hash_algo=full_hash,
            clean_names=clean_enabled,
            clean_copy_suffix=clean_copy_suffix or clean_names,
            clean_normalize_space=clean_normalize_space or clean_names,
            clean_remove_special=clean_remove_special or clean_names,
            conflict_suffix_width=effective_conflict_width,
            preset=WORK_PRESET,
        )
        st.write(f"來源檔案數量：{total_files}")
        st.write(f"重複檔案數量：{len(duplicate_matches)}")
        st.write(f"整理檔案數量：{len(organize_actions)}")
        st.write(f"報表輸出：{os.path.join(output, 'organize_report.csv')}")

        org_rows = [
            {
                "source": a.source_path,
                "dest": a.dest_path,
                "category": a.category,
                "conflict": "1" if a.name_conflict else "0",
            }
            for a in organize_actions
        ]
        st.subheader("整理清單")
        _ops_to_table(org_rows)

    if st.button("執行整理", disabled=not confirm, key="org_execute"):
        if dupe_strategy == "prefer-path" and not prefer_path:
            st.error("請輸入 prefer-path")
            return
        if not os.path.isdir(source):
            st.error("來源資料夾不存在")
            return
        clean_enabled = (
            clean_names or clean_copy_suffix or clean_normalize_space or clean_remove_special
        )
        effective_conflict_width = int(conflict_width) if clean_enabled else 1
        total_files, duplicate_matches, _, organize_actions = organize(
            source_folder=source,
            output_folder=output,
            recursive=recursive,
            time_partition=time_partition,
            dry_run=False,
            skip_duplicates=skip_duplicates,
            dupe_strategy=dupe_strategy,
            prefer_path=prefer_path if prefer_path else None,
            partial_size_mb=int(partial_size_mb),
            full_hash_algo=full_hash,
            clean_names=clean_enabled,
            clean_copy_suffix=clean_copy_suffix or clean_names,
            clean_normalize_space=clean_normalize_space or clean_names,
            clean_remove_special=clean_remove_special or clean_names,
            conflict_suffix_width=effective_conflict_width,
            preset=WORK_PRESET,
        )
        st.success(
            f"來源 {total_files} 個，已整理 {len(organize_actions)} 個，重複 {len(duplicate_matches)} 個。"
        )


def main() -> None:
    st.set_page_config(page_title="Duplicate File Finder", layout="wide")
    st.title("Duplicate File Finder / 工作檔案整理助手")
    mode = st.sidebar.radio("模式", ["重複檔案偵測", "工作檔案整理"], index=0)
    if mode == "重複檔案偵測":
        duplicate_finder_ui()
    else:
        organizer_ui()


if __name__ == "__main__":
    main()
