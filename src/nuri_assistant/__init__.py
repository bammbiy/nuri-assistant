"""Nuri Assistant: a desktop character secretary that talks to a local AI.

The companion lives in the domain packages (companion, schedule, todo, focus, pricewatch, voice)
and the Tk windows in ui/. The names re-exported below are the classic file-renaming tool's API,
kept at the top level for backward compatibility (tests and old scripts import them from here).
"""
__version__ = "0.1.0"  # keep in step with pyproject.toml

from .classic.core import (
    DEFAULT_EXTENSIONS,
    DEFAULT_RULE,
    RenameError,
    RenameInput,
    RenamePreview,
    apply_batch_rename,
    build_file_name,
    export_preview_csv,
    normalize_date,
    normalize_media,
    normalize_page,
    preview_batch,
    preview_rename,
    safe_name,
    scan_files,
    undo_last_batch,
)
from .classic.commands import FileAssistantPlan, interpret_file_command
from .classic.metadata import infer_metadata
from .classic.shopping import AIAdvice, ProductCandidate, PurchaseAssessment, ShoppingAdvisorError, advise_purchase, evaluate_purchase
from .classic.storage import HistoryStore, WorkProfile, load_profiles, save_profile

__all__ = [
    "__version__",
    "DEFAULT_EXTENSIONS",
    "DEFAULT_RULE",
    "AIAdvice",
    "FileAssistantPlan",
    "HistoryStore",
    "RenameError",
    "RenameInput",
    "RenamePreview",
    "ProductCandidate",
    "PurchaseAssessment",
    "ShoppingAdvisorError",
    "WorkProfile",
    "apply_batch_rename",
    "advise_purchase",
    "build_file_name",
    "export_preview_csv",
    "evaluate_purchase",
    "infer_metadata",
    "interpret_file_command",
    "load_profiles",
    "normalize_date",
    "normalize_media",
    "normalize_page",
    "preview_batch",
    "preview_rename",
    "safe_name",
    "save_profile",
    "scan_files",
    "undo_last_batch",
]
