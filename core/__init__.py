__version__ = "3.2.0"

from .actions import move_duplicates
from .dupe import GroupedFile, find_duplicates_between, group_duplicates, pick_keep_for_group
from .report import (
    duplicates_report_csv,
    organize_report_csv,
    orphans_report_csv,
    pairs_report_csv,
    write_duplicates_report,
    write_organize_report,
    write_pairs_report,
)
from .pairing import (
    JPG_EXTS_DEFAULT,
    RAW_EXTS_DEFAULT,
    PairAction,
    PairRecord,
    execute_pair_actions,
    pair_by_stem,
    plan_pair_layout,
)
from .media_scanner import scan_media_folder
from .media_types import MediaFileInfo, PhotoAction, PhotoPlan
from .naming import DestinationResolver, clean_filename, resolve_destination, safe_key_folder
from .oplog import default_log_path, make_record, read_oplog, write_oplog
from .paths import check_overlapping, path_is_within
from .photo_planner import plan_photo_actions
from .photo_executor import (
    duplicate_actions_to_records,
    execute_photo_actions,
    execute_duplicate_actions,
    photo_actions_to_records,
    write_actions_log,
)
from .organizer import organize, organize_actions_to_records
from .pairing import pair_actions_to_records
from .scanner import iter_files, scan_folder
from .similar import SimilarFile, find_similar_images
from .types import DuplicateAction, DuplicateMatch, FileInfo, OrganizeAction
from .undo import UndoAction, execute_undo, plan_undo, undo_from_log

__all__ = [
    "__version__",
    "DuplicateMatch",
    "DuplicateAction",
    "FileInfo",
    "OrganizeAction",
    "GroupedFile",
    "DestinationResolver",
    "find_duplicates_between",
    "group_duplicates",
    "pick_keep_for_group",
    "move_duplicates",
    "organize",
    "scan_folder",
    "iter_files",
    "clean_filename",
    "resolve_destination",
    "safe_key_folder",
    "check_overlapping",
    "path_is_within",
    "write_duplicates_report",
    "write_organize_report",
    "write_pairs_report",
    "duplicates_report_csv",
    "organize_report_csv",
    "pairs_report_csv",
    "orphans_report_csv",
    "JPG_EXTS_DEFAULT",
    "RAW_EXTS_DEFAULT",
    "PairRecord",
    "PairAction",
    "pair_by_stem",
    "plan_pair_layout",
    "execute_pair_actions",
    "scan_media_folder",
    "MediaFileInfo",
    "PhotoAction",
    "PhotoPlan",
    "plan_photo_actions",
    "execute_photo_actions",
    "execute_duplicate_actions",
    "photo_actions_to_records",
    "duplicate_actions_to_records",
    "organize_actions_to_records",
    "pair_actions_to_records",
    "write_actions_log",
    "make_record",
    "write_oplog",
    "read_oplog",
    "default_log_path",
    "UndoAction",
    "plan_undo",
    "execute_undo",
    "undo_from_log",
    "SimilarFile",
    "find_similar_images",
]
