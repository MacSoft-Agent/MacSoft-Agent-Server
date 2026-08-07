from types import SimpleNamespace

from tools.transcription_tools import (
    _LOGPROB_THRESHOLD_DEFAULT,
    _NO_SPEECH_PROB_THRESHOLD_DEFAULT,
    _is_hallucinated_segment,
    _join_confident_segments,
    build_local_transcribe_kwargs,
)


def _seg(text, no_speech_prob=0.0, avg_logprob=-0.2):
    return SimpleNamespace(text=text, no_speech_prob=no_speech_prob, avg_logprob=avg_logprob)


def test_local_kwargs_match_hardened_installed_defaults():
    kwargs = build_local_transcribe_kwargs({})
    assert kwargs["vad_filter"] is True
    assert kwargs["vad_parameters"] == {"min_silence_duration_ms": 500}
    assert kwargs["condition_on_previous_text"] is False
    assert kwargs["no_speech_threshold"] == _NO_SPEECH_PROB_THRESHOLD_DEFAULT
    assert kwargs["log_prob_threshold"] == _LOGPROB_THRESHOLD_DEFAULT


def test_request_language_keeps_macsoft_endpoint_precedence(monkeypatch):
    monkeypatch.delenv("HERMES_LOCAL_STT_LANGUAGE", raising=False)
    kwargs = build_local_transcribe_kwargs(
        {"language": "en", "local": {"language": "ja"}}, request_language="zh"
    )
    assert kwargs["language"] == "zh"


def test_initial_prompt_and_vad_are_configurable():
    kwargs = build_local_transcribe_kwargs(
        {"local": {"initial_prompt": "MacSoft AutoCount", "vad": False}}
    )
    assert kwargs["initial_prompt"] == "MacSoft AutoCount"
    assert kwargs["vad_filter"] is False


def test_confidence_gate_drops_only_probable_silence_hallucination():
    hallucination = _seg("Thank you.", no_speech_prob=0.95, avg_logprob=-1.5)
    quiet_speech = _seg("hello", no_speech_prob=0.8, avg_logprob=-0.3)
    assert _is_hallucinated_segment(hallucination, 0.6, -1.0)
    assert not _is_hallucinated_segment(quiet_speech, 0.6, -1.0)
    assert _join_confident_segments([quiet_speech, hallucination], {}) == "hello"
