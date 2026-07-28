"""Tests for the in-bot Privacy Policy disclosure (FixedFloat requirement #7)."""
from handlers.start import PRIVACY_TEXT, _privacy_text

TELEGRAM_MSG_LIMIT = 4096


def test_privacy_available_in_ru_and_en():
    assert "ru" in PRIVACY_TEXT and "en" in PRIVACY_TEXT


def test_privacy_text_within_telegram_limit():
    for lang, text in PRIVACY_TEXT.items():
        assert len(text) < TELEGRAM_MSG_LIMIT, f"{lang} too long"


def test_privacy_discloses_required_topics():
    text = PRIVACY_TEXT["en"].lower()
    # collection, association, provider recipient, retention, legal disclosure
    assert "telegram user id" in text
    assert "username" in text
    assert "fixedfloat" in text
    assert "one year" in text
    assert "law" in text


def test_privacy_fallback_to_english_for_unknown_lang():
    assert _privacy_text("xx") == PRIVACY_TEXT["en"]
    assert _privacy_text("ru") == PRIVACY_TEXT["ru"]
