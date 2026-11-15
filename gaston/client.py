"""Synchronous client for the Gaston API."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import IO, Any, BinaryIO, Iterable, Mapping, Tuple, Union
from urllib.parse import unquote

import requests

from .constants import (
    DIGEST_DETAIL_BRIEF,
    DIGEST_DETAILS,
    EXPORT_FORMATS,
    SUPPORTED_LANGUAGES,
    TRANSLATION_LANGUAGES,
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
    Digest,
    Directory,
    Media,
    MediaExport,
    MediaList,
    SearchResults,
    TranscribeResult,
    TranslateResult,
    User,
)

BASE_URL = "https://api.gaston.live"
# Undocumented escape hatch for development/testing only.
_BASE_URL_OVERRIDE_ENV = "GASTON_API_URL_OVERRIDE"

# Timeouts are passed straight to requests: a single value covers both connect
# and read; a (connect, read) tuple sets them separately; None waits forever.
TimeoutType = Union[float, Tuple[float, float], None]

# Quick metadata calls.
DEFAULT_TIMEOUT: TimeoutType = 30.0
# Endpoints that upload a file or fetch a remote URL can legitimately take
# minutes, so they get a much more generous read timeout by default.
DEFAULT_UPLOAD_TIMEOUT: TimeoutType = (10.0, 600.0)

# Chunk size used when streaming an export to disk.
_DOWNLOAD_CHUNK_SIZE = 1024 * 1024


class _Unset:
    """Sentinel for "argument not provided" (since None is a valid timeout)."""


_UNSET = _Unset()

_STATUS_EXCEPTIONS = {
    400: BadRequestError,
    403: AuthenticationError,
    404: NotFoundError,
    429: RateLimitError,
}


class GastonClient:
    """A client for the Gaston transcription/translation/search API.

    Args:
        token: API token (the ``gapi-...`` token issued by the platform).
            Falls back to the ``GASTON_API_TOKEN`` environment variable.
        timeout: Timeout for ordinary requests. A single float covers both
            connect and read; a ``(connect, read)`` tuple sets them separately;
            ``None`` waits indefinitely. Defaults to 30s.
        upload_timeout: Timeout for transferring media files (``transcribe``
            and audio exports), which can take minutes for large files.
            Defaults to ``(10s connect, 600s read)``.
        session: An optional pre-configured :class:`requests.Session`.

    Example::

        from gaston import GastonClient

        client = GastonClient(token="gapi-...")
        me = client.me()
        print(me.email, me.usage.files_left)

    The client can also be used as a context manager to ensure the underlying
    HTTP session is closed::

        with GastonClient(token="gapi-...") as client:
            client.transcribe("interview.mp4", lang="en")
    """

    def __init__(
        self,
        token: str | None = None,
        timeout: TimeoutType = DEFAULT_TIMEOUT,
        upload_timeout: TimeoutType = DEFAULT_UPLOAD_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        token = token or os.getenv("GASTON_API_TOKEN")
        if not token:
            raise GastonError(
                "An API token is required (pass token=... or set GASTON_API_TOKEN)."
            )
        self.token = token
        self.base_url = (os.getenv(_BASE_URL_OVERRIDE_ENV) or BASE_URL).rstrip("/")
        self.timeout = timeout
        self.upload_timeout = upload_timeout
        self._session = session or requests.Session()
        self._session.headers.update({"token": token})

    # -- context manager -------------------------------------------------

    def __enter__(self) -> "GastonClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    # -- low level -------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        timeout: TimeoutType | _Unset = _UNSET,
        digest: bool = False,
    ) -> Any:
        resp = self._send(method, path, params=params, files=files, timeout=timeout)
        return self._handle_response(resp, digest=digest)

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        timeout: TimeoutType | _Unset = _UNSET,
        stream: bool = False,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        # Drop params that are None so we don't send "dir_id=None" literally.
        clean_params = None
        if params is not None:
            clean_params = {k: v for k, v in params.items() if v is not None}

        try:
            resp = self._session.request(
                method,
                url,
                params=clean_params,
                files=files,
                timeout=self.timeout if isinstance(timeout, _Unset) else timeout,
                stream=stream,
            )
        except requests.RequestException as exc:
            raise GastonError(f"Request to {url} failed: {exc}") from exc

        return resp

    @staticmethod
    def _handle_response(resp: requests.Response, digest: bool = False) -> Any:
        try:
            body = resp.json()
        except ValueError:
            if resp.ok:
                return resp.text
            raise GastonAPIError(
                f"Non-JSON response from server: {resp.text[:200]}",
                status_code=resp.status_code,
            )

        # The API signals failures both via HTTP status codes and via an
        # ``error`` key in an otherwise 200 response. Handle both.
        error_message = body.get("error") if isinstance(body, dict) else None
        # A failed digest is a 2xx response carrying both ``digest_id`` and
        # ``error``; that is the digest's own state, not a failed request.
        if digest and resp.ok and isinstance(body, dict) and body.get("digest_id"):
            error_message = None

        if not resp.ok or error_message is not None:
            exc_cls = _STATUS_EXCEPTIONS.get(resp.status_code, GastonAPIError)
            details = None
            if isinstance(body, dict):
                details = (
                    body.get("details")
                    or body.get("supported_languages")
                    or body.get("supportedLanguages")
                )
            raise exc_cls(
                message=error_message or f"Request failed with status {resp.status_code}",
                status_code=resp.status_code,
                details=details,
                payload=body,
            )

        return body

    # -- user ------------------------------------------------------------

    def me(self) -> User:
        """Return the authenticated user and remaining usage."""
        return User.from_dict(self._request("GET", "/user/me"))

    # -- media -----------------------------------------------------------

    def list_media(self, page: int = 1, dir_id: int | None = None) -> MediaList:
        """List media in the library, paginated.

        Args:
            page: 1-based page number.
            dir_id: Restrict to a directory (``None`` for the root listing).
        """
        return MediaList.from_dict(
            self._request("GET", "/media/list", params={"page": page, "dir_id": dir_id})
        )

    def get_media(self, media_id: str, lang: str | None = None) -> Media:
        """Fetch a single media item including its sentences.

        Args:
            media_id: The public media id (``uid``).
            lang: Return sentences in this language (defaults to the original).
        """
        return Media.from_dict(
            self._request("GET", "/media", params={"media_id": media_id, "lang": lang})
        )

    def move_media(self, media_id: str, dir_id: int | None = None) -> Media:
        """Move a media item into a directory (``dir_id=None`` for root)."""
        return Media.from_dict(
            self._request("PATCH", "/media", params={"media_id": media_id, "dir_id": dir_id})
        )

    def transcribe(
        self,
        file: str | os.PathLike[str] | BinaryIO | IO[bytes],
        lang: str | None = None,
        dir_id: int | None = None,
        title: str | None = None,
        timeout: TimeoutType | _Unset = _UNSET,
    ) -> TranscribeResult:
        """Upload a media file and queue it for transcription.

        Args:
            file: Path to a file, or an already-open binary file object.
            lang: Source language hint (see :data:`SUPPORTED_LANGUAGES`). If
                omitted the language is auto-detected.
            dir_id: Directory to place the media into.
            title: Display title (defaults to the file name).
            timeout: Override the client's ``upload_timeout`` for this call.

        Returns:
            A :class:`TranscribeResult` with the new media id and state.
        """
        if lang is not None and lang not in SUPPORTED_LANGUAGES:
            raise BadRequestError(
                f"Language '{lang}' is not supported.", details=list(SUPPORTED_LANGUAGES)
            )

        params = {"lang": lang, "dir_id": dir_id, "title": title}

        should_close = False
        if isinstance(file, (str, os.PathLike)):
            fh: IO[bytes] = open(file, "rb")
            should_close = True
        else:
            fh = file
        effective_timeout = self.upload_timeout if isinstance(timeout, _Unset) else timeout
        try:
            files = {"file": fh}
            data = self._request(
                "POST", "/media/transcribe", params=params, files=files, timeout=effective_timeout
            )
        finally:
            if should_close:
                fh.close()
        return TranscribeResult.from_dict(data)

    def transcribe_url(
        self,
        url: str,
        lang: str | None = None,
        dir_id: int | None = None,
    ) -> TranscribeResult:
        """Queue transcription of a remote media URL (YouTube or web).

        Args:
            url: The media URL to download and transcribe.
            lang: Source language hint (see :data:`SUPPORTED_LANGUAGES`).
            dir_id: Directory to place the media into.
        """
        if lang is not None and lang not in SUPPORTED_LANGUAGES:
            raise BadRequestError(
                f"Language '{lang}' is not supported.", details=list(SUPPORTED_LANGUAGES)
            )
        data = self._request(
            "POST", "/media/transcribe-url", params={"url": url, "lang": lang, "dir_id": dir_id}
        )
        return TranscribeResult.from_dict(data)

    def translate(self, media_id: str, target_lang: str) -> TranslateResult:
        """Queue a translation of a transcribed media into ``target_lang``.

        Args:
            media_id: The public media id.
            target_lang: Target language short code (see
                :data:`TRANSLATION_LANGUAGES`).
        """
        target_lang = target_lang.lower().strip()
        if target_lang not in TRANSLATION_LANGUAGES:
            raise BadRequestError(
                f"Language '{target_lang}' is not a supported translation target.",
                details=list(TRANSLATION_LANGUAGES),
            )
        data = self._request(
            "PATCH", "/media/translate", params={"media_id": media_id, "target_lang": target_lang}
        )
        return TranslateResult.from_dict(data)

    def align_translation(
        self,
        media_id: str,
        target_lang: str,
        clamp: bool | None = None,
    ) -> AlignTranslationResult:
        """Queue word-level alignment of a translation against source timestamps.

        Produces per-word start/end times for ``target_lang`` (for karaoke-style
        playback), based on the source-language WhisperX timestamps.

        Args:
            media_id: The public media id.
            target_lang: Target language short code; must already be fully
                translated (``available_languages[target_lang] == 100``) or the
                API returns a 400.
            clamp: Force non-decreasing timestamps across a sentence. If
                omitted, the worker uses its own default.
        """
        target_lang = target_lang.lower().strip()
        if target_lang not in TRANSLATION_LANGUAGES:
            raise BadRequestError(
                f"Language '{target_lang}' is not a supported translation target.",
                details=list(TRANSLATION_LANGUAGES),
            )
        data = self._request(
            "PATCH",
            "/media/align-translation",
            params={"media_id": media_id, "target_lang": target_lang, "clamp": clamp},
        )
        return AlignTranslationResult.from_dict(data)

    def diarize(
        self,
        media_id: str,
        lang: str,
        speakers: int | None = None,
    ) -> TranscribeResult:
        """Queue speaker diarization for a (translated) media in ``lang``.

        Args:
            media_id: The public media id.
            lang: Language of the transcript to diarize (must be fully
                translated first).
            speakers: Optional expected number of speakers.
        """
        data = self._request(
            "PATCH",
            "/media/diarize",
            params={"media_id": media_id, "lang": lang, "speakers": speakers},
        )
        return TranscribeResult.from_dict(data)

    def export_media(
        self,
        media_id: str,
        format: str,
        lang: str | None = None,
        max_words_per_block: int = 0,
        include_speakers: bool = False,
        timeout: TimeoutType | _Unset = _UNSET,
    ) -> MediaExport:
        """Export a media item's transcript (or audio) as a file, in memory.

        For large audio files prefer :meth:`export_media_to_file`, which
        streams to disk instead of holding the whole file in memory.

        Args:
            media_id: The public media id.
            format: One of :data:`EXPORT_FORMATS`: ``text``,
                ``text_timestamps``, ``csv``, ``srt`` or ``audio``. Exporting
                audio, or any media longer than 30 minutes, requires a paid
                plan.
            lang: Language of the transcript to export (defaults to the
                original). For ``audio``, a finished dubbed track in this
                language is returned if one exists.
            max_words_per_block: ``srt`` only: split sentences into subtitle
                blocks of at most this many words (``0`` keeps whole
                sentences).
            include_speakers: ``srt`` only: prefix subtitles with speaker names
                (requires diarization).
            timeout: Override the timeout for this call. Defaults to the
                client's ``upload_timeout`` for ``audio`` and ``timeout``
                otherwise.

        Returns:
            A :class:`MediaExport` with the file content and the filename
            suggested by the server.
        """
        resp = self._send_export(
            media_id, format, lang, max_words_per_block, include_speakers, timeout
        )
        with resp:
            try:
                content = resp.content
            except requests.RequestException as exc:
                raise GastonError(f"Downloading export of '{media_id}' failed: {exc}") from exc
            return MediaExport(
                content=content,
                filename=_filename_from_disposition(resp.headers.get("Content-Disposition")),
                content_type=resp.headers.get("Content-Type"),
            )

    def export_media_to_file(
        self,
        media_id: str,
        path: str | os.PathLike[str],
        format: str,
        lang: str | None = None,
        max_words_per_block: int = 0,
        include_speakers: bool = False,
        timeout: TimeoutType | _Unset = _UNSET,
    ) -> Path:
        """Export a media item and stream it straight to ``path``.

        Takes the same arguments as :meth:`export_media`. If ``path`` is an
        existing directory, the file is written inside it using the filename
        suggested by the server.

        Returns:
            The path the file was written to.
        """
        resp = self._send_export(
            media_id, format, lang, max_words_per_block, include_speakers, timeout
        )
        with resp:
            target = Path(path)
            if target.is_dir():
                filename = _filename_from_disposition(resp.headers.get("Content-Disposition"))
                if not filename:
                    raise GastonError("The server did not suggest a filename; pass a file path.")
                target = target / filename
            try:
                with open(target, "wb") as fh:
                    for chunk in resp.iter_content(_DOWNLOAD_CHUNK_SIZE):
                        fh.write(chunk)
            except requests.RequestException as exc:
                target.unlink(missing_ok=True)
                raise GastonError(f"Downloading export of '{media_id}' failed: {exc}") from exc
            except BaseException:
                target.unlink(missing_ok=True)
                raise
        return target

    def _send_export(
        self,
        media_id: str,
        format: str,
        lang: str | None,
        max_words_per_block: int,
        include_speakers: bool,
        timeout: TimeoutType | _Unset,
    ) -> requests.Response:
        if format not in EXPORT_FORMATS:
            raise BadRequestError(
                f"Export format '{format}' is not supported.", details=list(EXPORT_FORMATS)
            )
        if max_words_per_block < 0:
            raise BadRequestError("max_words_per_block cannot be negative.")
        if isinstance(timeout, _Unset) and format == "audio":
            timeout = self.upload_timeout

        resp = self._send(
            "GET",
            "/media/export",
            params={
                "media_id": media_id,
                "format": format,
                "lang": lang,
                # Leave server defaults implicit.
                "max_words_per_block": max_words_per_block or None,
                "include_speakers": include_speakers or None,
            },
            timeout=timeout,
            stream=True,
        )
        # Successful exports are never JSON (a transcript might still happen to
        # parse as JSON, so don't sniff the body); errors always are.
        content_type = resp.headers.get("Content-Type", "")
        if not resp.ok or content_type.startswith("application/json"):
            with resp:
                self._handle_response(resp)
                raise GastonAPIError(
                    "Unexpected JSON response to an export request.",
                    status_code=resp.status_code,
                )
        return resp

    # -- digest ----------------------------------------------------------

    def create_digest(
        self,
        url: str,
        lang: str | None = None,
        dir_id: int | None = None,
        detail: str = DIGEST_DETAIL_BRIEF,
        question: str | None = None,
        answer_lang: str | None = None,
    ) -> Digest:
        """Add the media behind ``url`` and request an AI digest of it.

        The media is added like :meth:`transcribe_url`; the digest is a summary
        and, optionally, the answer to a question. It is generated once the
        media is transcribed: poll :meth:`get_digest` or use
        :meth:`wait_for_digest`. Requesting the same digest of the same media
        again returns the existing one.

        Args:
            url: The media URL (YouTube or web).
            lang: Source language hint (see :data:`SUPPORTED_LANGUAGES`).
            dir_id: Directory to place the media into.
            detail: One of :data:`DIGEST_DETAILS`: ``brief`` or ``detailed``.
            question: A question to answer from the transcript (at most 2000
                characters).
            answer_lang: Language of the summary and answer. Validated by the
                server, whose list differs from :data:`SUPPORTED_LANGUAGES`.

        Returns:
            A :class:`Digest` with only the ids and states set; the rest comes
            from :meth:`get_digest`.
        """
        if lang is not None and lang not in SUPPORTED_LANGUAGES:
            raise BadRequestError(
                f"Language '{lang}' is not supported.", details=list(SUPPORTED_LANGUAGES)
            )
        if detail not in DIGEST_DETAILS:
            raise BadRequestError(
                f"Digest detail '{detail}' is not supported.", details=list(DIGEST_DETAILS)
            )
        data = self._request(
            "POST",
            "/digest",
            params={
                "url": url,
                "lang": lang,
                "dir_id": dir_id,
                # Leave the server default implicit.
                "detail": None if detail == DIGEST_DETAIL_BRIEF else detail,
                "question": question,
                "answer_lang": answer_lang,
            },
        )
        return Digest.from_dict(data)

    def get_digest(self, digest_id: str) -> Digest:
        """Fetch a digest and its current state.

        A digest that failed is returned (with :attr:`Digest.is_failed` true
        and :attr:`Digest.error` set) rather than raised, so polling code can
        tell a failed digest from a failed request.

        Args:
            digest_id: The digest id returned by :meth:`create_digest`.
        """
        return Digest.from_dict(
            self._request("GET", "/digest", params={"digest_id": digest_id}, digest=True)
        )

    def wait_for_digest(
        self,
        digest_id: str,
        timeout: float | None = 900.0,
        interval: float = 10.0,
    ) -> Digest:
        """Poll a digest until it is ready or has failed.

        Transcribing a long recording takes minutes, hence the generous
        default timeout.

        Args:
            digest_id: The digest id returned by :meth:`create_digest`.
            timeout: Give up after this many seconds (``None`` waits
                indefinitely).
            interval: Seconds to wait between polls.

        Returns:
            A finished :class:`Digest`; check :attr:`Digest.is_failed`.

        Raises:
            GastonError: If the digest is not finished within ``timeout``.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            digest = self.get_digest(digest_id)
            if digest.is_finished:
                return digest
            wait = max(0.0, interval)
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise GastonError(
                        f"Digest '{digest_id}' was not finished within {timeout} seconds "
                        f"(last state: {digest.digest_state or 'unknown'})."
                    )
                wait = min(wait, remaining)
            if wait > 0:
                time.sleep(wait)

    # -- directories -----------------------------------------------------

    def directory_tree(self) -> dict[str, Any]:
        """Return the full nested directory tree for the user."""
        return self._request("GET", "/directory/tree")

    def create_directory(self, title: str, dir_id: int | None = None) -> Directory:
        """Create a directory, optionally nested under ``dir_id``."""
        return Directory.from_dict(
            self._request("POST", "/directory", params={"title": title, "dir_id": dir_id})
        )

    def delete_directory(self, dir_id: int) -> bool:
        """Delete a directory. Returns ``True`` on success."""
        data = self._request("DELETE", "/directory", params={"dir_id": dir_id})
        return bool(data.get("result")) if isinstance(data, dict) else bool(data)

    def update_directory(
        self,
        dir_id: int,
        title: str,
        parent_id: int | None = None,
    ) -> Directory:
        """Rename a directory and/or move it under ``parent_id``."""
        return Directory.from_dict(
            self._request(
                "PATCH",
                "/directory",
                params={"dir_id": dir_id, "title": title, "parent_id": parent_id},
            )
        )

    # -- search ----------------------------------------------------------

    def search(
        self,
        query: str,
        from_: int = 0,
        max_: int = 50,
        dir_ids: Iterable[str | int] | None = None,
        lang: str | None = None,
        media_id: str | None = None,
    ) -> SearchResults:
        """Search for sentences across all transcribed media.

        The query supports a subset of the Lucene ``query_string`` syntax:

        * Boolean operators ``AND`` / ``OR`` / ``NOT`` (e.g. ``cats AND dogs``).
        * Grouping with parentheses (e.g. ``(cats OR dogs) AND vet``).
        * Quoted phrases for exact matches (e.g. ``"climate change"``).
        * Trailing wildcards (e.g. ``transcri*``). Leading wildcards
          (``*tion``) are not allowed and are stripped.

        Field selectors, fuzzy/proximity (``~``), boosts (``^``) and ranges are
        stripped server-side.

        Args:
            query: Full text query (must be at least 3 characters).
            from_: Offset of the first result (for pagination).
            max_: Maximum number of results to return.
            dir_ids: Restrict the search to one or more directory ids.
            lang: Restrict the search to a single language.
            media_id: Restrict the search to a single media item.
        """
        if len(query) < 3:
            raise BadRequestError("Query must be at least 3 characters.")
        params: dict[str, Any] = {
            "query": query,
            "_from": from_,
            "_max": max_,
            "lang": lang,
            "media_id": media_id,
        }
        if dir_ids is not None:
            params["dir_ids"] = [str(d) for d in dir_ids]
        return SearchResults.from_dict(self._request("GET", "/sentence/search", params=params))


def _filename_from_disposition(header: str | None) -> str | None:
    """Extract the filename from a ``Content-Disposition`` header.

    Prefers the RFC 5987 ``filename*`` (UTF-8) form over the ASCII fallback.
    """
    if not header:
        return None
    match = re.search(r"filename\*\s*=\s*([^']*)'[^']*'([^;]+)", header, re.IGNORECASE)
    if match:
        name = unquote(match.group(2).strip(), encoding=match.group(1) or "utf-8")
    else:
        match = re.search(r'filename\s*=\s*"([^"]*)"|filename\s*=\s*([^;]+)', header, re.IGNORECASE)
        if not match:
            return None
        name = (match.group(1) if match.group(1) is not None else match.group(2)).strip()
    # Never let a server-supplied name escape the target directory.
    name = os.path.basename(name.replace("\\", "/"))
    return name if name not in ("", ".", "..") else None
