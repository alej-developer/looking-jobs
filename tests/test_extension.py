"""The browser extension must not submit applications."""

from pathlib import Path


def test_extension_does_not_click_submit():
    script = Path(__file__).resolve().parent.parent / "extension" / "content.js"
    text = script.read_text(encoding="utf-8")
    assert ".click(" not in text
    assert "type=\"submit\"" not in text
    assert "127.0.0.1:8000" in text
    assert "chrome.storage.local" not in text
