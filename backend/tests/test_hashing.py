from app.ingestion import content_hash
import pytest

def test_same_text_gives_same_hash():
    assert content_hash("hello") == content_hash("hello")

def test_empty_content_raises():
    with pytest.raises(ValueError):
        content_hash(" ")
