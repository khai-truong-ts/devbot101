import pytest
from bot import config as cfg
from bot import guardrail


def test_allowed_channel_accepted():
    cfg.ALLOWED_CHANNEL_IDS = "C123,C456"
    cfg.ALLOWED_USER_IDS = ""
    assert guardrail.is_allowed_channel("C123") is True


def test_unknown_channel_rejected():
    cfg.ALLOWED_CHANNEL_IDS = "C123"
    cfg.ALLOWED_USER_IDS = ""
    assert guardrail.is_allowed_channel("C999") is False


def test_empty_allowlist_rejects_all():
    cfg.ALLOWED_CHANNEL_IDS = ""
    cfg.ALLOWED_USER_IDS = ""
    assert guardrail.is_allowed_channel("C123") is False


def test_allowed_user_bypasses_channel_check():
    cfg.ALLOWED_CHANNEL_IDS = ""
    cfg.ALLOWED_USER_IDS = "U001"
    assert guardrail.is_allowed_channel("C_ANYTHING", user_id="U001") is True


def test_sanitize_truncates():
    long_text = "a" * 5000
    result = guardrail.sanitize_prompt(long_text, include_prefix=False)
    assert len(result) == 4000


def test_sanitize_adds_prefix():
    result = guardrail.sanitize_prompt("hello")
    assert result.startswith("[SYSTEM:")
