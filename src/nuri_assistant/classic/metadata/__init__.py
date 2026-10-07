"""Guesses date, media code and page from a document's file name."""
from .inference import infer_metadata
from .patterns import DATE_PATTERN, MEDIA_CODE_PATTERN, PAGE_PATTERN

__all__ = ["DATE_PATTERN", "MEDIA_CODE_PATTERN", "PAGE_PATTERN", "infer_metadata"]
