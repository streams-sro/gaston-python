"""Tests for GastonClient using mocked HTTP responses."""

import io

import pytest
import responses

from gaston import (
    AuthenticationError,
    BadRequestError,
    GastonAPIError,
    GastonClient,
    GastonError,
    NotFoundError,
    RateLimitError,
)

BASE = "http://test.local"


@pytest.fixture
def client(monkeypatch):
    # The base URL is fixed; tests point it at the mock server via the
    # undocumented override env var.
    monkeypatch.setenv("GASTON_API_URL_OVERRIDE", BASE)
    return GastonClient(token="gapi-test")


@responses.activate
def test_me(client):
    responses.add(
        responses.GET,
        f"{BASE}/user/me",
        json={"id": "u1", "email": "a@b.c", "enabled": True, "usage": {"filesLeft": 7}},
    )
    me = client.me()
    assert me.id == "u1"
    assert me.email == "a@b.c"
    assert me.enabled is True
    assert me.usage.files_left == 7
    # token header is sent
    assert responses.calls[0].request.headers["token"] == "gapi-test"


@responses.activate
def test_list_media_skips_none_params(client):
    responses.add(
        responses.GET,
        f"{BASE}/media/list",
        json={
            "media": [
                {"id": "m1", "title": "T", "state": "transcribed",
                 "available_languages": {"sk": 100}, "directory_id": None},
            ],
            "total": 1,
            "pages": 1,
        },
    )
    result = client.list_media(page=2)
    assert len(result) == 1
    assert result.total == 1
    item = list(result)[0]
    assert item.id == "m1"
    assert item.title == "T"
    assert item.available_languages == {"sk": 100}
    assert item.directory_id is None
    # dir_id was None and must not be sent
    assert "dir_id" not in responses.calls[0].request.url
    assert "page=2" in responses.calls[0].request.url


@responses.activate
def test_get_media_parses_sentences(client):
    responses.add(
        responses.GET,
        f"{BASE}/media",
        json={
            "id": "m1",
            "title": "T",
            "state": "transcribed",
            "available_languages": {"en": 100},
            "sentences": [{"id": 1, "body": "hi", "speaker": "A"}],
            "diarized_sentences": {},
        },
    )
    media = client.get_media("m1", lang="en")
    assert media.title == "T"
    assert media.sentences[0].text == "hi"
    assert media.sentences[0].speaker == "A"
    assert media.available_languages == {"en": 100}


@responses.activate
def test_move_media_returns_media(client):
    responses.add(
        responses.PATCH,
        f"{BASE}/media",
        json={
            "id": "m1",
            "title": "T",
            "state": "transcribed",
            "file": "https://cdn.example.com/m1.mp4",
            "available_languages": {"en": 100},
            "sentences": [],
            "diarized_sentences": {},
            "dir_id": 5,
        },
    )
    media = client.move_media("m1", dir_id=5)
    assert media.id == "m1"
    assert media.file == "https://cdn.example.com/m1.mp4"
    assert media.directory_id == 5
    assert "dir_id=5" in responses.calls[0].request.url


@responses.activate
def test_transcribe_from_fileobj(client):
    responses.add(
        responses.POST,
        f"{BASE}/media/transcribe",
        json={"id": "me123", "state": "uploaded"},
    )
    fh = io.BytesIO(b"fake audio")
    result = client.transcribe(fh, title="clip")
    assert result.id == "me123"
    assert result.state == "uploaded"


def test_transcribe_rejects_bad_lang(client):
    with pytest.raises(BadRequestError):
        client.transcribe(io.BytesIO(b"x"), lang="zz")


def test_translate_rejects_bad_lang(client):
    with pytest.raises(BadRequestError):
        client.translate("m1", target_lang="zz")


@responses.activate
def test_translate(client):
    responses.add(
        responses.PATCH,
        f"{BASE}/media/translate",
        json={"id": "m1", "available_languages": {"en": 100, "de": 0}},
    )
    result = client.translate("m1", target_lang="DE")
    assert result.available_languages["de"] == 0
    assert "target_lang=de" in responses.calls[0].request.url


def test_align_translation_rejects_bad_lang(client):
    with pytest.raises(BadRequestError):
        client.align_translation("m1", target_lang="zz")


@responses.activate
def test_align_translation(client):
    responses.add(
        responses.PATCH,
        f"{BASE}/media/align-translation",
        json={"id": "m1", "target_lang": "de", "alignment_progress": 0},
    )
    result = client.align_translation("m1", target_lang="DE", clamp=False)
    assert result.id == "m1"
    assert result.target_lang == "de"
    assert result.alignment_progress == 0
    url = responses.calls[0].request.url
    assert "target_lang=de" in url
    assert "clamp=False" in url


@responses.activate
def test_align_translation_omits_clamp_when_unset(client):
    responses.add(
        responses.PATCH,
        f"{BASE}/media/align-translation",
        json={"id": "m1", "target_lang": "de", "alignment_progress": 0},
    )
    client.align_translation("m1", target_lang="de")
    assert "clamp" not in responses.calls[0].request.url


@responses.activate
def test_export_media_text(client):
    responses.add(
        responses.GET,
        f"{BASE}/media/export",
        body="Hello world.\n".encode("utf-8"),
        content_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=\"zaznam\"; "
                                   "filename*=UTF-8''Z%C3%A1znam.txt",
        },
    )
    export = client.export_media("m1", "text", lang="sk")
    assert export.text == "Hello world.\n"
    assert export.filename == "Záznam.txt"
    assert export.content_type.startswith("text/plain")
    url = responses.calls[0].request.url
    assert "media_id=m1" in url and "format=text" in url and "lang=sk" in url
    # srt-only defaults must not be sent
    assert "max_words_per_block" not in url
    assert "include_speakers" not in url


@responses.activate
def test_export_media_json_like_transcript_is_not_parsed(client):
    # A transcript that happens to be valid JSON must still come back as text.
    responses.add(
        responses.GET, f"{BASE}/media/export", body=b"123",
        content_type="text/plain; charset=utf-8",
    )
    assert client.export_media("m1", "text").content == b"123"


@responses.activate
def test_export_media_srt_options(client):
    responses.add(
        responses.GET, f"{BASE}/media/export", body=b"1\n",
        content_type="application/x-subrip; charset=utf-8",
    )
    client.export_media("m1", "srt", max_words_per_block=8, include_speakers=True)
    url = responses.calls[0].request.url
    assert "max_words_per_block=8" in url
    assert "include_speakers=True" in url


@responses.activate
def test_export_media_error(client):
    responses.add(
        responses.GET,
        f"{BASE}/media/export",
        json={"error": "Media 'm1' not found."},
        status=404,
    )
    with pytest.raises(NotFoundError):
        client.export_media("m1", "csv")


@responses.activate
def test_export_media_paid_plan_error(client):
    responses.add(
        responses.GET,
        f"{BASE}/media/export",
        json={"error": "Exporting audio requires a paid plan."},
        status=403,
    )
    with pytest.raises(AuthenticationError) as exc:
        client.export_media("m1", "audio")
    assert "paid plan" in str(exc.value)


def test_export_media_rejects_bad_format(client):
    with pytest.raises(BadRequestError):
        client.export_media("m1", "pdf")


def test_export_media_rejects_negative_block_size(client):
    with pytest.raises(BadRequestError):
        client.export_media("m1", "srt", max_words_per_block=-1)


@responses.activate
def test_export_media_to_file_uses_server_filename(client, tmp_path):
    responses.add(
        responses.GET,
        f"{BASE}/media/export",
        body=b"\x00audio-bytes",
        content_type="audio/mpeg",
        headers={"Content-Disposition": 'attachment; filename="../../evil.mp3"'},
    )
    path = client.export_media_to_file("m1", tmp_path, "audio")
    assert path == tmp_path / "evil.mp3"
    assert path.read_bytes() == b"\x00audio-bytes"


@responses.activate
def test_export_media_to_file_explicit_path(client, tmp_path):
    responses.add(
        responses.GET, f"{BASE}/media/export", body=b"a,b\n",
        content_type="text/csv; charset=utf-8",
    )
    target = tmp_path / "out.csv"
    assert client.export_media_to_file("m1", target, "csv") == target
    assert target.read_bytes() == b"a,b\n"


@responses.activate
def test_export_media_to_file_error_writes_nothing(client, tmp_path):
    responses.add(
        responses.GET, f"{BASE}/media/export",
        json={"error": "No transcription found."}, status=404,
    )
    target = tmp_path / "out.txt"
    with pytest.raises(NotFoundError):
        client.export_media_to_file("m1", target, "text")
    assert not target.exists()


@responses.activate
def test_search_builds_params(client):
    responses.add(
        responses.GET,
        f"{BASE}/sentence/search",
        json={
            "results": [
                {"_sentence": {"body": "a"}, "_highlight": {"body": ["<hlt>a</hlt>"]}},
                {"_sentence": {"body": "b"}, "_highlight": {"body": ["<hlt>b</hlt>"]}},
            ],
            "total": {"value": 2, "relation": "eq"},
        },
    )
    results = client.search("hello world", from_=0, max_=10, dir_ids=[1, 2], lang="en")
    assert len(results) == 2
    assert results.total == 2
    assert results.results[0]["_sentence"]["body"] == "a"
    url = responses.calls[0].request.url
    assert "_from=0" in url and "_max=10" in url
    assert "dir_ids=1" in url and "dir_ids=2" in url


def test_search_too_short(client):
    with pytest.raises(BadRequestError):
        client.search("hi")


@responses.activate
def test_auth_error_from_status(client):
    responses.add(
        responses.GET,
        f"{BASE}/user/me",
        json={"error": "Token is invalid or user is disabled"},
        status=403,
    )
    with pytest.raises(AuthenticationError):
        client.me()


@responses.activate
def test_rate_limit_error(client):
    responses.add(
        responses.POST,
        f"{BASE}/media/transcribe",
        json={"error": "File limit reached"},
        status=429,
    )
    with pytest.raises(RateLimitError):
        client.transcribe(io.BytesIO(b"x"))


@responses.activate
def test_error_key_on_200_response(client):
    # The API sometimes returns an error body with a 200 status.
    responses.add(
        responses.POST,
        f"{BASE}/media/transcribe-url",
        json={"error": "This URL isn't supported or may be private."},
        status=200,
    )
    with pytest.raises(Exception) as exc:
        client.transcribe_url("http://x")
    assert "supported" in str(exc.value)


def test_delete_directory_returns_bool(client):
    with responses.RequestsMock() as rsps:
        rsps.add(responses.DELETE, f"{BASE}/directory", json={"result": True})
        assert client.delete_directory(5) is True


@responses.activate
def test_create_digest(client):
    responses.add(
        responses.POST,
        f"{BASE}/digest",
        json={"id": "me1", "state": "pending", "digest_id": "dg1", "digest_state": "pending"},
    )
    digest = client.create_digest(
        "https://youtu.be/x", lang="en", dir_id=5, detail="detailed",
        question="Who is speaking?", answer_lang="ga",
    )
    assert (digest.id, digest.state) == ("me1", "pending")
    assert (digest.digest_id, digest.digest_state) == ("dg1", "pending")
    assert digest.detail is None and digest.question is None and digest.language is None
    assert digest.transcription_progress is None
    assert digest.summary is None and digest.answer is None and digest.error is None
    assert not digest.is_finished

    request = responses.calls[0].request
    assert request.method == "POST"
    assert request.params == {
        "url": "https://youtu.be/x",
        "lang": "en",
        "dir_id": "5",
        "detail": "detailed",
        "question": "Who is speaking?",
        # Not in SUPPORTED_LANGUAGES; the server validates answer_lang.
        "answer_lang": "ga",
    }


@responses.activate
def test_create_digest_omits_defaults(client):
    responses.add(responses.POST, f"{BASE}/digest", json={"id": "me1", "digest_id": "dg1"})
    client.create_digest("https://youtu.be/x")
    assert responses.calls[0].request.params == {"url": "https://youtu.be/x"}


@responses.activate
def test_create_digest_rejects_bad_lang_and_detail(client):
    with pytest.raises(BadRequestError):
        client.create_digest("https://youtu.be/x", lang="xx")
    with pytest.raises(BadRequestError) as exc:
        client.create_digest("https://youtu.be/x", detail="huge")
    assert exc.value.details == ["brief", "detailed"]
    assert len(responses.calls) == 0


@responses.activate
def test_create_digest_unsupported_answer_lang(client):
    responses.add(
        responses.POST,
        f"{BASE}/digest",
        json={"error": "This answer language is not supported.",
              "supported_languages": ["en", "ga"]},
        status=400,
    )
    with pytest.raises(BadRequestError) as exc:
        client.create_digest("https://youtu.be/x", answer_lang="yue")
    assert exc.value.details == ["en", "ga"]


@responses.activate
def test_create_digest_error_key_on_200_raises(client):
    responses.add(
        responses.POST, f"{BASE}/digest",
        json={"error": "This URL isn't supported or may be private."}, status=200,
    )
    with pytest.raises(GastonAPIError):
        client.create_digest("http://x")


@responses.activate
def test_get_digest_pending(client):
    responses.add(
        responses.GET,
        f"{BASE}/digest",
        json={
            "id": "me1", "state": "uploaded", "digest_id": "dg1", "digest_state": "pending",
            "detail": "brief", "question": None, "custom_email": None,
            "transcription_progress": 40,
        },
    )
    digest = client.get_digest("dg1")
    assert digest.state == "uploaded"
    assert digest.digest_state == "pending"
    assert digest.detail == "brief"
    assert digest.transcription_progress == 40
    assert digest.summary is None
    assert not digest.is_ready and not digest.is_failed and not digest.is_finished

    request = responses.calls[0].request
    assert request.method == "GET"
    assert request.params == {"digest_id": "dg1"}
    assert request.headers["token"] == "gapi-test"


@responses.activate
def test_get_digest_ready_without_answer(client):
    responses.add(
        responses.GET,
        f"{BASE}/digest",
        json={
            "id": "me1", "state": "transcribed", "digest_id": "dg1", "digest_state": "ready",
            "detail": "detailed", "question": None, "language": "en",
            "summary": {
                "text": "It is about bees [S1-S2].",
                "citations": [{"marker": "[S1-S2]", "title": "Bees", "sentence_ids": [1, 2],
                               "start": 0.5, "end": 7.25}],
            },
        },
    )
    digest = client.get_digest("dg1")
    assert digest.is_ready and digest.is_finished and not digest.is_failed
    assert digest.language == "en"
    assert digest.summary.text == "It is about bees [S1-S2]."
    assert digest.summary.error is None
    (citation,) = digest.summary.citations
    assert citation.marker == "[S1-S2]"
    assert citation.title == "Bees"
    assert citation.sentence_ids == [1, 2]
    assert (citation.start, citation.end) == (0.5, 7.25)
    assert digest.answer is None
    assert digest.raw["digest_state"] == "ready"


@responses.activate
def test_get_digest_ready_with_answer(client):
    responses.add(
        responses.GET,
        f"{BASE}/digest",
        json={
            "digest_id": "dg1", "digest_state": "ready", "question": "Who?", "language": "en",
            "summary": {"text": "Summary.", "citations": []},
            "answer": {
                "text": "Alice [S3].",
                "citations": [{"marker": "[S3]", "title": None, "sentence_ids": [3],
                               "start": None, "end": None}],
            },
        },
    )
    digest = client.get_digest("dg1")
    assert digest.question == "Who?"
    assert digest.summary.citations == []
    assert digest.answer.text == "Alice [S3]."
    assert digest.answer.error is None
    assert digest.answer.citations[0].sentence_ids == [3]
    assert digest.answer.citations[0].start is None


@responses.activate
def test_get_digest_ready_with_failed_answer(client):
    responses.add(
        responses.GET,
        f"{BASE}/digest",
        json={
            "digest_id": "dg1", "digest_state": "ready", "question": "Who?", "language": "en",
            "summary": {"text": "Summary.", "citations": []},
            "answer": {"text": None, "citations": [], "error": "model unavailable"},
        },
    )
    digest = client.get_digest("dg1")
    assert digest.is_ready and not digest.is_failed
    assert digest.summary.text == "Summary."
    assert digest.answer.text is None
    assert digest.answer.error == "model unavailable"
    assert digest.error is None


@responses.activate
def test_get_digest_error_on_200_returns_digest(client):
    responses.add(
        responses.GET,
        f"{BASE}/digest",
        json={"id": "me1", "state": "error", "digest_id": "dg1", "digest_state": "error",
              "detail": "brief", "error": "media processing failed"},
        status=200,
    )
    digest = client.get_digest("dg1")
    assert digest.is_failed and digest.is_finished and not digest.is_ready
    assert digest.error == "media processing failed"
    assert digest.summary is None


@responses.activate
def test_get_digest_ai_disabled(client):
    responses.add(
        responses.GET, f"{BASE}/digest",
        json={"error": "AI features are disabled for this account."}, status=403,
    )
    with pytest.raises(AuthenticationError):
        client.get_digest("dg1")


@responses.activate
def test_get_digest_not_found(client):
    responses.add(
        responses.GET, f"{BASE}/digest", json={"error": "Digest 'dg1' not found."}, status=404
    )
    with pytest.raises(NotFoundError):
        client.get_digest("dg1")


@responses.activate
def test_wait_for_digest_polls_until_finished(client):
    for payload in (
        {"digest_id": "dg1", "digest_state": "pending"},
        {"digest_id": "dg1", "digest_state": "generating"},
        {"digest_id": "dg1", "digest_state": "error", "error": "boom"},
    ):
        responses.add(responses.GET, f"{BASE}/digest", json=payload)
    digest = client.wait_for_digest("dg1", timeout=5, interval=0)
    assert digest.is_failed
    assert digest.error == "boom"
    assert len(responses.calls) == 3


@responses.activate
def test_wait_for_digest_times_out(client):
    responses.add(
        responses.GET, f"{BASE}/digest", json={"digest_id": "dg1", "digest_state": "generating"}
    )
    with pytest.raises(GastonError) as exc:
        client.wait_for_digest("dg1", timeout=0.05, interval=0.03)
    assert not isinstance(exc.value, GastonAPIError)
    assert "generating" in str(exc.value)


def test_requires_token(monkeypatch):
    monkeypatch.delenv("GASTON_API_TOKEN", raising=False)
    with pytest.raises(Exception):
        GastonClient()


def test_default_base_url(monkeypatch):
    monkeypatch.delenv("GASTON_API_URL_OVERRIDE", raising=False)
    client = GastonClient(token="gapi-test")
    assert client.base_url == "https://api.gaston.live"
