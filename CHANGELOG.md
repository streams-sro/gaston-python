# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/).

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

[0.2.0]: https://github.com/streams-guru/gaston-python/releases/tag/v0.2.0