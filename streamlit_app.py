"""檔案整理工具 Streamlit UI 入口。各模式實作在 ui/ 套件。"""
from __future__ import annotations

import streamlit as st

from core import __version__
from ui.common import show_history_sidebar
from ui.dupe import duplicate_finder_ui
from ui.single_dupe import single_folder_dedupe_ui
from ui.organizer import organizer_ui
from ui.pairing import pairing_ui
from ui.photo import photo_organizer_ui
from ui.similar import similar_photos_ui
from ui.undo_ui import undo_ui

_MODES = {
    "🔍 重複檔案偵測": duplicate_finder_ui,
    "🧹 單資料夾去重": single_folder_dedupe_ui,
    "🪞 相似照片偵測": similar_photos_ui,
    "📁 工作檔案整理": organizer_ui,
    "📷 RAW/JPG 配對": pairing_ui,
    "🎞️ 攝影素材整理": photo_organizer_ui,
    "↩️ 復原操作": undo_ui,
}


def main() -> None:
    st.set_page_config(
        page_title="檔案整理工具",
        page_icon="📁",
        layout="wide",
    )

    st.sidebar.title("📁 檔案整理工具")
    st.sidebar.markdown("---")

    mode = st.sidebar.radio(
        "選擇功能",
        list(_MODES.keys()),
        index=0,
        label_visibility="collapsed",
    )

    show_history_sidebar()

    st.sidebar.markdown("---")
    st.sidebar.caption(f"v{__version__} | 使用 Streamlit 建置")

    _MODES[mode]()


if __name__ == "__main__":
    main()
