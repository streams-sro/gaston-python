"""Constants mirrored from the Gaston API.

These are kept in sync with the server so the client can validate input
locally before issuing a request.
"""

from __future__ import annotations

#: Languages accepted by the transcription endpoints (Whisper language codes).
SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs", "ca", "cs", "cy", "da", "de",
    "el", "en", "es", "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi", "hr", "ht",
    "hu", "hy", "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb", "ln", "lo", "lt",
    "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", "ne", "nl", "nn", "no", "oc", "pa", "pl",
    "ps", "pt", "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw", "ta",
    "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "zh", "yue",
)

#: Languages the translation endpoint can translate into (short code -> FLORES code).
TRANSLATION_OPTIONS: dict[str, str] = {
    "en": "eng_Latn", "de": "deu_Latn", "es": "spa_Latn", "pl": "pol_Latn", "hu": "hun_Latn",
    "cs": "ces_Latn", "sk": "slk_Latn", "uk": "ukr_Cyrl", "bg": "bul_Cyrl", "hr": "hrv_Latn",
    "da": "dan_Latn", "nl": "nld_Latn", "et": "est_Latn", "fi": "fin_Latn", "fr": "fra_Latn",
    "el": "ell_Grek", "it": "ita_Latn", "lv": "lav_Latn", "lt": "lit_Latn", "mt": "mlt_Latn",
    "pt": "por_Latn", "ro": "ron_Latn", "sl": "slv_Latn", "sv": "swe_Latn", "zh": "zho_Hans",
    "ar": "arb_Arab", "hi": "hin_Deva", "ja": "jpn_Jpan", "id": "ind_Latn", "is": "isl_Latn",
    "he": "heb_Hebr", "kk": "kaz_Cyrl", "ko": "kor_Hang", "lb": "ltz_Latn", "mk": "mkd_Cyrl",
    "tr": "tur_Latn", "vi": "vie_Latn", "bn": "ben_Beng", "be": "bel_Cyrl", "ka": "kat_Geor",
    "fa": "pes_Arab", "ur": "urd_Arab", "te": "tel_Telu", "ru": "rus_Cyrl",
}

#: Languages available as translation targets.
TRANSLATION_LANGUAGES: tuple[str, ...] = tuple(TRANSLATION_OPTIONS.keys())

#: Possible values of ``Media.state``.
MEDIA_STATE_PENDING = "pending"
MEDIA_STATE_UPLOADED = "uploaded"
MEDIA_STATE_TRANSCRIBED = "transcribed"

#: Possible values of ``Media.origin``.
MEDIA_ORIGIN_UPLOADED = "up"
MEDIA_ORIGIN_YOUTUBE = "yt"
MEDIA_ORIGIN_WEB = "web"