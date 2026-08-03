"""Tests for _normalize_chat_content in the API server adapter."""

from gateway.platforms import api_server
from gateway.platforms.api_server import (
    _html_document_payload,
    _is_dashboard_request,
    _is_html_document,
    _normalize_chat_content,
)


class TestHtmlDashboardContract:
    def test_complete_html_document_is_recognized(self):
        assert _is_html_document("<!doctype html>\n<html><body>ok</body></html>")
        assert not _is_html_document("<div>not a document</div>")
        assert not _is_html_document("```html\n<!doctype html>...</html>\n```")

    def test_dashboard_request_detection(self):
        assert _is_dashboard_request("给我 debtor dashboard，有 chart")
        assert not _is_dashboard_request("列出所有 debtor")

    def test_html_event_payload_is_explicit(self):
        payload = _html_document_payload(
            "<!doctype html><html></html>",
            message_id="msg_1",
            session_id="sess_1",
        )
        assert payload == {
            "schema_version": 1,
            "message_id": "msg_1",
            "session_id": "sess_1",
            "mime_type": "text/html",
            "html": "<!doctype html><html></html>",
        }


class TestNormalizeChatContent:
    """Content normalization converts array-based content parts to plain text."""

    def test_none_returns_empty_string(self):
        assert _normalize_chat_content(None) == ""

    def test_plain_string_returned_as_is(self):
        assert _normalize_chat_content("hello world") == "hello world"

    def test_empty_string_returned_as_is(self):
        assert _normalize_chat_content("") == ""

    def test_text_content_part(self):
        content = [{"type": "text", "text": "hello"}]
        assert _normalize_chat_content(content) == "hello"

    def test_input_text_content_part(self):
        content = [{"type": "input_text", "text": "user input"}]
        assert _normalize_chat_content(content) == "user input"

    def test_output_text_content_part(self):
        content = [{"type": "output_text", "text": "assistant output"}]
        assert _normalize_chat_content(content) == "assistant output"

    def test_multiple_text_parts_joined_with_newline(self):
        content = [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]
        assert _normalize_chat_content(content) == "first\nsecond"

    def test_mixed_string_and_dict_parts(self):
        content = ["plain string", {"type": "text", "text": "dict part"}]
        assert _normalize_chat_content(content) == "plain string\ndict part"

    def test_image_url_parts_silently_skipped(self):
        content = [
            {"type": "text", "text": "check this:"},
            {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
        ]
        assert _normalize_chat_content(content) == "check this:"

    def test_integer_content_converted(self):
        assert _normalize_chat_content(42) == "42"

    def test_boolean_content_converted(self):
        assert _normalize_chat_content(True) == "True"

    def test_deeply_nested_list_respects_depth_limit(self):
        """Nesting beyond max_depth returns empty string."""
        content = [[[[[[[[[[[["deep"]]]]]]]]]]]]
        result = _normalize_chat_content(content)
        # The deep nesting should be truncated, not crash
        assert isinstance(result, str)

    def test_large_list_capped(self):
        """Lists beyond MAX_CONTENT_LIST_SIZE are truncated."""
        content = [{"type": "text", "text": f"item{i}"} for i in range(2000)]
        result = _normalize_chat_content(content)
        # Should not contain all 2000 items
        assert result.count("item") <= 1000

    def test_oversized_string_truncated(self):
        """Strings beyond 64KB are truncated."""
        huge = "x" * 100_000
        result = _normalize_chat_content(huge)
        assert len(result) == 65_536

    def test_empty_text_parts_filtered(self):
        content = [
            {"type": "text", "text": ""},
            {"type": "text", "text": "actual"},
            {"type": "text", "text": ""},
        ]
        assert _normalize_chat_content(content) == "actual"

    def test_dict_without_type_skipped(self):
        content = [{"foo": "bar"}, {"type": "text", "text": "real"}]
        assert _normalize_chat_content(content) == "real"

    def test_empty_list_returns_empty(self):
        assert _normalize_chat_content([]) == ""

    def test_many_small_parts_normalize_without_quadratic_rescan(self, monkeypatch):
        """Large content arrays should normalize in linear time."""
        content = [{"type": "text", "text": "x"} for _ in range(1000)]
        sum_calls = 0

        def counting_sum(values):
            nonlocal sum_calls
            sum_calls += 1
            return sum(values)

        monkeypatch.setattr(api_server, "sum", counting_sum, raising=False)
        result = _normalize_chat_content(content)

        assert result.count("x") == 1000
        assert sum_calls == 0
