from .actions import move_duplicates
from .dupe import find_duplicates_between, group_duplicates
from .report import write_duplicates_report
from .scanner import scan_folder
from .types import DuplicateAction, DuplicateMatch, FileInfo

__all__ = [
    "DuplicateMatch",
    "DuplicateAction",
    "FileInfo",
    "find_duplicates_between",
    "group_duplicates",
    "move_duplicates",
    "scan_folder",
    "write_duplicates_report",
]
