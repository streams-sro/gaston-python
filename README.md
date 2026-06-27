# Gaston API Client

[![PyPI version](https://img.shields.io/pypi/v/gaston.svg)](https://pypi.org/project/gaston/)
[![Python versions](https://img.shields.io/pypi/pyversions/gaston.svg)](https://pypi.org/project/gaston/)
[![License: MIT](https://img.shields.io/pypi/l/gaston.svg)](https://pypi.org/project/gaston/)

A small, typed Python client for the **Gaston API**: transcription, translation
and full-text search of sentences within transcribed recordings.

> Requires a Gaston account and an API token (see [Configuration](#configuration)).

## Installation

```bash
pip install gaston
```

Requires Python 3.10+.

For local development from a checkout instead:

```bash
pip install -e .
```

## Quick start

```python
from gaston import GastonClient

client = GastonClient(token="gapi-...")

# Who am I + remaining quota
me = client.me()
print(me.email, "files left:", me.usage.files_left)

# Transcribe a local file
result = client.transcribe("interview.mp4", lang="en", title="My interview")
print(result.id, result.state)

# Transcribe from a URL (YouTube or web)
client.transcribe_url("https://youtu.be/dQw4w9WgXcQ", lang="en")

# Translate an existing transcription
client.translate(result.id, target_lang="de")

# Speaker diarization (requires a completed translation in that language)
client.diarize(result.id, lang="de", speakers=2)

# Fetch a media item with its sentences
media = client.get_media(result.id, lang="en")
for sentence in media.sentences:
    print(sentence.id, sentence.text, sentence.speaker)

# Full text search across the whole library
results = client.search("climate change", max_=20)
print("total matches:", results.total)
for hit in results:
    print(hit["_sentence"]["body"], "->", hit["_highlight"]["body"])
```

See [Search](#search) for query syntax and filtering options.

### Configuration

Generate an API token in the Gaston app under
[Settings -> API](https://www.gaston.live/user/settings/api/en). Full endpoint
documentation is available at <https://www.gaston.live/en/api>.

The token can be supplied directly or via an environment variable:

| Argument | Environment variable | Default    |
|----------|----------------------|------------|
| `token`  | `GASTON_API_TOKEN`   | (required) |

```python
# Uses GASTON_API_TOKEN from the environment
with GastonClient() as client:
    ...
```

### Timeouts

Ordinary requests use a 30s timeout. The file upload in `transcribe` can take
minutes for large files, so it uses a separate, more generous `upload_timeout`
(default `(10s connect, 600s read)`).

A timeout may be a single float, a `(connect, read)` tuple, or `None` to wait
indefinitely.

```python
# Customise the defaults for all calls
client = GastonClient(
    token="gapi-...",
    timeout=30,
    upload_timeout=(10, 1800),   # allow up to 30 min to upload large files
)

# Or override per call (e.g. no read timeout for a very large file)
client.transcribe("huge-recording.mp4", timeout=(10, None))
```

## Directories

```python
folder = client.create_directory("Podcasts")
client.update_directory(folder.id, title="Podcast archive")
client.move_media(media_id="me...", dir_id=folder.id)
tree = client.directory_tree()
client.delete_directory(folder.id)
```

## Search

`client.search(query, from_=0, max_=50, dir_ids=None, lang=None)` runs a
full-text search over every sentence in your transcribed media.

### Query syntax

The query supports a subset of the Lucene `query_string` syntax:

| Feature           | Example                  | Notes                                    |
|-------------------|--------------------------|------------------------------------------|
| Boolean `AND`     | `cats AND dogs`          | both terms must appear                    |
| Boolean `OR`      | `cats OR dogs`           | either term                              |
| Boolean `NOT`     | `cats NOT dogs`          | exclude a term                           |
| Grouping          | `(cats OR dogs) AND vet` | combine operators with parentheses       |
| Exact phrase      | `"climate change"`       | quoted terms match as a phrase           |
| Trailing wildcard | `transcri*`              | matches `transcribe`, `transcription`... |

Leading wildcards (`*tion`), field selectors, fuzzy (`~`), boosts (`^`) and
ranges are not supported and are stripped server-side. Queries must be at least
3 characters.

```python
results = client.search('(invoice OR receipt) AND "due date" NOT draft')
```

### Filtering and pagination

```python
# Search within a single directory
client.search("budget", dir_ids=[42])

# Search across several directories
client.search("budget", dir_ids=[42, 43, 7])

# Restrict to one language, and page through results
page2 = client.search("budget", from_=50, max_=50, lang="en")
```

### Reading results

`search()` returns a `SearchResults` object. Iterate it for hits, or read
`.total` for the overall match count. Each hit is a dict with:

- `_sentence` - the matched sentence plus its `media` metadata (id, title,
  duration, directory, thumbnail, file, originUrl).
- `_highlight` - matched fragments with the hit terms wrapped in
  `<hlt>...</hlt>` tags.

```python
results = client.search("climate change", max_=20)
print("total matches:", results.total)
for hit in results:
    sentence = hit["_sentence"]
    print(sentence["media"]["title"], "|", hit["_highlight"]["body"])
```

## Error handling

All failures raise a subclass of `GastonError`:

```python
from gaston import GastonClient, AuthenticationError, RateLimitError, NotFoundError

try:
    client.transcribe("clip.mp4")
except RateLimitError:
    print("File limit reached")
except AuthenticationError:
    print("Bad token / disabled account")
except NotFoundError as e:
    print("Not found:", e.message)
```

| Exception             | Trigger                                  |
|-----------------------|------------------------------------------|
| `AuthenticationError` | HTTP 403, invalid token / disabled user  |
| `BadRequestError`     | HTTP 400, invalid parameters             |
| `NotFoundError`       | HTTP 404, resource not found             |
| `RateLimitError`      | HTTP 429, usage limit exceeded           |
| `GastonAPIError`      | any other API error                      |

Every exception carries `.status_code`, `.message`, `.details` and the raw
`.payload`.

## Supported languages

```python
from gaston import SUPPORTED_LANGUAGES, TRANSLATION_LANGUAGES
```

`SUPPORTED_LANGUAGES` lists transcription source languages; `TRANSLATION_LANGUAGES`
lists the available translation targets.
