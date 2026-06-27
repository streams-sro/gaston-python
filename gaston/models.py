"""Typed models for Gaston API responses.

Every model keeps the original decoded payload in ``raw`` so that fields not
explicitly mapped here are still accessible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Usage:
    """Account usage information."""

    files_left: int
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Usage":
        return cls(files_left=data.get("filesLeft", 0), raw=data)


@dataclass
class User:
    """The authenticated user (``GET /user/me``)."""

    id: str
    email: str
    enabled: bool
    usage: Usage
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "User":
        return cls(
            id=data.get("id"),
            email=data.get("email"),
            enabled=data.get("enabled", False),
            usage=Usage.from_dict(data.get("usage", {})),
            raw=data,
        )


@dataclass
class Sentence:
    """A single transcribed (or translated) sentence."""

    id: int | None
    speaker: Any | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Sentence":
        return cls(id=data.get("id"), speaker=data.get("speaker"), raw=data)

    @property
    def text(self) -> str | None:
        return self.raw.get("text") or self.raw.get("sentence")


@dataclass
class Media:
    """Full media detail (``GET /media``)."""

    id: str
    title: str | None
    state: str | None
    origin: str | None
    origin_url: str | None
    file: str | None
    error: str | None
    thumbnail: str | None
    duration: int | None
    published_at: Any | None
    added_at: Any | None
    transcription_progress: int | None
    download_progress: int | None
    language: str | None
    available_languages: dict[str, Any]
    sentences: list[Sentence]
    diarized_sentences: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Media":
        return cls(
            id=data.get("id"),
            title=data.get("title"),
            state=data.get("state"),
            origin=data.get("origin"),
            origin_url=data.get("originUrl"),
            file=data.get("file"),
            error=data.get("error"),
            thumbnail=data.get("thumbnail"),
            duration=data.get("duration"),
            published_at=data.get("published_at"),
            added_at=data.get("added_at"),
            transcription_progress=data.get("transcription_progress"),
            download_progress=data.get("download_progress"),
            language=data.get("language"),
            available_languages=data.get("available_languages") or {},
            sentences=[Sentence.from_dict(s) for s in data.get("sentences") or []],
            diarized_sentences=data.get("diarized_sentences") or {},
            raw=data,
        )


@dataclass
class MediaList:
    """A page of media items (``GET /media/list``)."""

    media: list[dict[str, Any]]
    total: int
    pages: int
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MediaList":
        return cls(
            media=data.get("media") or [],
            total=data.get("total", 0),
            pages=data.get("pages", 0),
            raw=data,
        )

    def __iter__(self):
        return iter(self.media)

    def __len__(self) -> int:
        return len(self.media)


@dataclass
class TranscribeResult:
    """Result of a transcription request (``id`` + ``state``)."""

    id: str
    state: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscribeResult":
        return cls(id=data.get("id"), state=data.get("state"), raw=data)


@dataclass
class TranslateResult:
    """Result of a translation request."""

    id: str
    available_languages: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranslateResult":
        return cls(
            id=data.get("id"),
            available_languages=data.get("available_languages") or {},
            raw=data,
        )


@dataclass
class Directory:
    """A directory in the user's library."""

    id: int | None
    title: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Directory":
        return cls(id=data.get("id"), title=data.get("title"), raw=data)


@dataclass
class SearchResults:
    """Results of a sentence search (``GET /sentence/search``).

    Each entry in :attr:`results` is a dict with two keys: ``_sentence`` (the
    matched sentence and its ``media`` metadata) and ``_highlight`` (the matched
    fragments with ``<hlt>...</hlt>`` markers around the hit terms).
    """

    results: list[dict[str, Any]]
    total: int | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SearchResults":
        results: list[dict[str, Any]] = []
        total: int | None = None
        if isinstance(data, dict):
            results = data.get("results") or []
            # ``total`` is an Elasticsearch total object: {"value": N, ...}.
            total_obj = data.get("total")
            if isinstance(total_obj, dict):
                total = total_obj.get("value")
            elif isinstance(total_obj, int):
                total = total_obj
        return cls(results=results, total=total, raw=data)

    def __iter__(self):
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)