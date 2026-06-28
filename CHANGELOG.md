# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/).

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

[0.4.0]: https://github.com/streams-sro/gaston-python/releases/tag/v0.4.0
[0.3.0]: https://github.com/streams-sro/gaston-python/releases/tag/v0.3.0
[0.2.0]: https://github.com/streams-sro/gaston-python/releases/tag/v0.2.0