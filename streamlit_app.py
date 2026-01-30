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


def _parse_exts_text(value: str, defaults: set[str]) -> set[str]:
    items = {v.strip().lower() for v in value.split(",") if v.strip()}
    if not items:
        return defaults
    normalized = set()
    for ext in items:
        normalized.add(ext if ext.startswith(".") else f".{ext}")
    return normalized


def pairing_ui() -> None:
    st.header("RAW/JPG 配對工具")
    with st.expander("使用說明", expanded=True):
        st.markdown(
            "\n".join(
                [
                    "1. 選擇 JPG 與 RAW 資料夾，並設定輸出資料夾。",
                    "2. 選擇模式：copy-raw（只複製 RAW）或 pair-organize（成對整理）。",
                    "3. 建議先按「一鍵預覽」，確認 pairs / orphans 清單。",
                    "4. 勾選確認後再執行。",
                ]
            )
        )

    col1, col2 = st.columns(2)
    with col1:
        jpg_folder = st.text_input("JPG 資料夾", value="folder1")
    with col2:
        raw_folder = st.text_input("RAW 資料夾", value="folder2")
    output_folder = st.text_input("輸出資料夾", value="pair_output")

    st.subheader("模式與配對設定")
    mode = st.selectbox(
        "模式",
        ["copy-raw", "pair-organize"],
        index=0,
    )
    recursive = st.checkbox("遞迴掃描子資料夾", value=False)
    key_mode = st.selectbox("配對 key", ["stem", "stem+parent"], index=0)

    st.subheader("副檔名設定")
    jpg_exts_text = st.text_input(
        "JPG 副檔名（逗號分隔）",
        value=",".join(sorted(JPG_EXTS_DEFAULT)),
    )
    raw_exts_text = st.text_input(
        "RAW 副檔名（逗號分隔）",
        value=",".join(sorted(RAW_EXTS_DEFAULT)),
    )

    st.subheader("成對整理設定（pair-organize）")
    layout = st.selectbox(
        "整理布局",
        ["raw-with-jpg", "per-pair-folder", "split-index"],
        index=0,
    )
    use_move = st.checkbox("使用移動（Move）", value=False)

    confirm = st.checkbox("我了解這將複製/移動檔案", value=False)

    if st.button("一鍵預覽"):
        if not os.path.isdir(jpg_folder) or not os.path.isdir(raw_folder):
            st.error("資料夾不存在")
            return

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

        st.write(f"配對成功：{len(pairs)}")
        st.write(f"孤兒 JPG：{len(orphan_jpgs)}")
        st.write(f"孤兒 RAW：{len(orphan_raws)}")

        report_pairs = os.path.join(output_folder, "pairs.csv")
        report_orphans = os.path.join(output_folder, "orphans.csv")
        write_pairs_report(pairs, orphan_jpgs, orphan_raws, report_pairs, report_orphans)
        st.write(f"報表輸出：{report_pairs}")
        st.write(f"報表輸出：{report_orphans}")

        pair_rows = [
            {"key": p.key, "jpg": p.jpg_path, "raw": p.raw_path} for p in pairs
        ]
        orphan_rows = (
            [{"type": "jpg", "path": p} for p in orphan_jpgs]
            + [{"type": "raw", "path": p} for p in orphan_raws]
        )
        st.subheader("Pairs")
        _ops_to_table(pair_rows)
        st.subheader("Orphans")
        _ops_to_table(orphan_rows)

    if st.button("執行", disabled=not confirm):
        if not os.path.isdir(jpg_folder) or not os.path.isdir(raw_folder):
            st.error("資料夾不存在")
            return

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

        report_pairs = os.path.join(output_folder, "pairs.csv")
        report_orphans = os.path.join(output_folder, "orphans.csv")
        write_pairs_report(pairs, orphan_jpgs, orphan_raws, report_pairs, report_orphans)

        if mode == "copy-raw":
            actions = plan_pair_layout(
                pairs,
                output_folder,
                layout="raw-with-jpg",
                action="copy",
                conflict_suffix_width=3,
            )
            raw_actions = [a for a in actions if a.role == "raw"]
            copied, _ = execute_pair_actions(
                raw_actions,
                dry_run=False,
                move=False,
            )
            st.success(f"完成 RAW 複製：{copied}")
            return

        actions = plan_pair_layout(
            pairs,
            output_folder,
            layout=layout,
            action="move" if use_move else "copy",
            conflict_suffix_width=3,
        )
        copied, _ = execute_pair_actions(
            actions,
            dry_run=False,
            move=use_move,
        )
        st.success(f"完成成對整理：{copied}")


def photo_organizer_ui() -> None:
    st.header("攝影素材整理")
    with st.expander("使用說明", expanded=True):
        st.markdown(
            "\n".join(
                [
                    "1. 選擇來源與輸出資料夾。",
                    "2. 選擇配對 key 與輸出布局。",
                    "3. 建議先按「一鍵預覽」，查看 pairs / orphans / duplicates。",
                    "4. 勾選確認後執行。",
                ]
            )
        )

    source = st.text_input("來源資料夾", value=".")
    output = st.text_input("輸出資料夾", value="photo_output")
    recursive = st.checkbox("遞迴掃描子資料夾", value=True)

    st.subheader("配對與輸出")
    layout = st.selectbox("輸出布局", ["by-date-type", "per-pair-folder"], index=0)
    pair_key = st.selectbox("配對 key", ["stem", "stem+parent", "exif"], index=0)

    st.subheader("重複檔案偵測")
    enable_duplicates = st.checkbox("啟用重複檔案偵測", value=True)
    dupe_strategy = st.selectbox("保留策略", ["latest", "earliest", "prefer-path"], index=0)
    prefer_path = st.text_input("prefer-path（選填）", value="")
    partial_size_mb = st.number_input("partial hash 大小（MB）", min_value=1, value=1)
    full_hash = st.selectbox("完整 hash", ["sha256", "xxhash64"], index=0, key="photo_full_hash")

    st.subheader("執行設定")
    use_move = st.checkbox("使用移動（Move）", value=False)
    confirm = st.checkbox("我了解這將移動/複製檔案", value=False)

    if st.button("一鍵預覽", key="photo_preview"):
        if not os.path.isdir(source):
            st.error("來源資料夾不存在")
            return
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
            partial_size_mb=int(partial_size_mb),
            full_hash_algo=full_hash,
            conflict_suffix_width=3,
        )

        st.write(f"來源檔案：{len(plan.media_files)}")
        st.write(f"配對成功：{len(plan.pairs)}")
        st.write(f"孤兒 JPG：{len(plan.orphan_jpgs)}")
        st.write(f"孤兒 RAW：{len(plan.orphan_raws)}")
        st.write(f"重複檔案：{len(plan.duplicate_matches)}")
        st.write(f"整理項目：{len(plan.photo_actions)}")

        pairs_path = os.path.join(output, "pairs.csv")
        orphans_path = os.path.join(output, "orphans.csv")
        pair_records = [PairRecord(key=p[0], jpg_path=p[1], raw_path=p[2]) for p in plan.pairs]
        write_pairs_report(pair_records, plan.orphan_jpgs, plan.orphan_raws, pairs_path, orphans_path)
        st.write(f"pairs.csv：{pairs_path}")
        st.write(f"orphans.csv：{orphans_path}")

        if plan.duplicate_matches:
            duplicates_path = os.path.join(output, "duplicates_report.csv")
            write_duplicates_report(plan.duplicate_matches, duplicates_path, plan.duplicate_actions)
            st.write(f"duplicates_report.csv：{duplicates_path}")

        pair_rows = [{"key": p[0], "jpg": p[1], "raw": p[2]} for p in plan.pairs]
        orphan_rows = (
            [{"type": "jpg", "path": p} for p in plan.orphan_jpgs]
            + [{"type": "raw", "path": p} for p in plan.orphan_raws]
        )
        st.subheader("Pairs")
        _ops_to_table(pair_rows)
        st.subheader("Orphans")
        _ops_to_table(orphan_rows)

    if st.button("執行整理", disabled=not confirm, key="photo_execute"):
        if not os.path.isdir(source):
            st.error("來源資料夾不存在")
            return
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
            partial_size_mb=int(partial_size_mb),
            full_hash_algo=full_hash,
            conflict_suffix_width=3,
        )

        pairs_path = os.path.join(output, "pairs.csv")
        orphans_path = os.path.join(output, "orphans.csv")
        pair_records = [PairRecord(key=p[0], jpg_path=p[1], raw_path=p[2]) for p in plan.pairs]
        write_pairs_report(pair_records, plan.orphan_jpgs, plan.orphan_raws, pairs_path, orphans_path)

        completed_duplicates = execute_duplicate_actions(plan.duplicate_actions, dry_run=False)
        completed_actions = execute_photo_actions(plan.photo_actions, dry_run=False, move=use_move)
        log_path = os.path.join(output, "actions_log.jsonl")
        write_actions_log(completed_actions, completed_duplicates, log_path)

        if plan.duplicate_matches:
            duplicates_path = os.path.join(output, "duplicates_report.csv")
            write_duplicates_report(plan.duplicate_matches, duplicates_path, plan.duplicate_actions)

        st.success(f"已完成整理：{len(completed_actions)}")


def main() -> None:
    st.set_page_config(page_title="Duplicate File Finder", layout="wide")
    st.title("Duplicate File Finder / 工作檔案整理助手")
    mode = st.sidebar.radio(
        "模式",
        ["重複檔案偵測", "工作檔案整理", "RAW/JPG 配對工具", "攝影素材整理"],
        index=0,
    )
    if mode == "重複檔案偵測":
        duplicate_finder_ui()
    elif mode == "工作檔案整理":
        organizer_ui()
    elif mode == "RAW/JPG 配對工具":
        pairing_ui()
    else:
        photo_organizer_ui()


if __name__ == "__main__":
    main()
