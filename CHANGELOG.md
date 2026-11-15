# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [0.8.0] - 2026-11-15

### Added
- `create_digest()` to add the media behind a URL and request an AI digest of
  it (a `brief` or `detailed` summary, optionally with the answer to a
  question), `get_digest()` to fetch it, and `wait_for_digest()` to poll until
  it is ready or has failed (default timeout 900s, polling every 10s).
- `Digest`, `DigestText` and `DigestCitation` models. A failed digest is
  returned with `Digest.is_failed` true rather than raised, even though the
  API reports it with an `error` key.
- `DIGEST_DETAILS` constant, plus `DIGEST_STATE_*` and `DIGEST_DETAIL_*` in
  `gaston.constants`. The digest answer language is validated by the server,
  not against `SUPPORTED_LANGUAGES`.

## [0.7.0] - 2026-10-04

### Added
- `export_media()` to export a media item as `text`, `text_timestamps`, `csv`,
  `srt` or `audio`, returning a `MediaExport` (content, server-suggested
  filename and content type). `srt` exports support `max_words_per_block` and
  `include_speakers`.
- `export_media_to_file()` to stream an export straight to disk (recommended
  for audio).
- `EXPORT_FORMATS` constant listing the supported export formats.

## [0.6.0] - 2026-07-07

### Added
- `align_translation()` to queue word-level alignment of a translated sentence
  set against source-language timestamps, for karaoke-style playback. Progress
  is surfaced via the new `Media.translation_alignment` field (and via the
  returned `AlignTranslationResult.alignment_progress`).

### Changed
- `move_media()` now returns a `Media` object (matching `get_media()`'s shape)
  instead of a raw dict, since the API response was fixed to no longer leak
  internal ids.

## [0.5.0] - 2026-07-04

### Added
- `search()` accepts a `media_id` parameter to restrict results to a single
  media item.

## [0.4.0] - 2026-06-28

### Fixed
- `Sentence.text` now reads the API's `body` field, so sentences from
  `get_media()` return their text instead of `None`.

### Changed
- `list_media()` now returns `Media` objects for each item instead of raw dicts,
  matching `get_media()` and `search()`. Iterating a `MediaList` yields `Media`
  (e.g. `item.id`, `item.title`), so code relying on dict access
  (`item["id"]`) must be updated.

### Added
- `Media.directory_id`, populated by `list_media()` (it is `None` for
  `get_media()`, which does not return it).

## [0.3.0] - 2026-06-27

### Changed
- Point repository URLs (`Source`, `Changelog`) at
  `github.com/streams-sro/gaston-python`.

## [0.2.0] - 2026-06-27

First public release on PyPI (`pip install gaston`).

### Added
- `GastonClient` covering the full Gaston API: user, media (transcribe, upload,
  transcribe-url, translate, diarize), directories and sentence search.
- Typed response models (`User`, `Media`, `MediaList`, `Sentence`, `Directory`,
  `TranscribeResult`, `TranslateResult`, `SearchResults`).
- Exception hierarchy (`AuthenticationError`, `BadRequestError`,
  `NotFoundError`, `RateLimitError`) raised from API errors.
- Separate, generous `upload_timeout` for the file-upload endpoint.
- Documented search query syntax (`AND`/`OR`/`NOT`, grouping, phrases, trailing
  wildcards) and directory/language filtering.

### Fixed
- `SearchResults` now parses the real `{"results": [...], "total": {...}}`
  response shape (previously assumed a raw Elasticsearch payload).

[0.5.0]: https://github.com/streams-sro/gaston-python/releases/tag/v0.5.0
[0.4.0]: https://github.com/streams-sro/gaston-python/releases/tag/v0.4.0
[0.3.0]: https://github.com/streams-sro/gaston-python/releases/tag/v0.3.0
[0.2.0]: https://github.com/streams-sro/gaston-python/releases/tag/v0.2.0