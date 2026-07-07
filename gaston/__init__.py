"""Python client library for the Gaston API.

Transcription, translation and full-text search of sentences within
transcribed recordings.
"""

from __future__ import annotations

from .client import GastonClient
from .constants import (
    SUPPORTED_LANGUAGES,
    TRANSLATION_LANGUAGES,
    TRANSLATION_OPTIONS,
)
from .exceptions import (
    AuthenticationError,
    BadRequestError,
    GastonAPIError,
    GastonError,
    NotFoundError,
    RateLimitError,
)
from .models import (
    AlignTranslationResult,
    Directory,
    Media,
    MediaList,
    SearchResults,
    Sentence,
    TranscribeResult,
    TranslateResult,
    Usage,
    User,
)

__version__ = "0.6.0"

__all__ = [
    "GastonClient",
    # exceptions
    "GastonError",
    "GastonAPIError",
    "AuthenticationError",
    "BadRequestError",
    "NotFoundError",
    "RateLimitError",
    # models
    "User",
    "Usage",
    "Media",
    "MediaList",
    "Sentence",
    "Directory",
    "TranscribeResult",
    "TranslateResult",
    "AlignTranslationResult",
    "SearchResults",
    # constants
    "SUPPORTED_LANGUAGES",
    "TRANSLATION_LANGUAGES",
    "TRANSLATION_OPTIONS",
]