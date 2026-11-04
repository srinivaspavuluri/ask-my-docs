from app.prompts import load_prompt
import pytest

def test_answer_v1_has_all_placeholders():
    template = load_prompt("answer_v1")
    assert "{refusal}" in template
    assert "{context}" in template
    assert "{question}" in template

def test_answer_v1_formats_without_error():
    template = load_prompt("answer_v1")
    text = template.format(refusal="REFUSAL_X", context="CONTEXT_X", question="QUESTION_X")
    assert "REFUSAL_X" in text
    assert "CONTEXT_X" in text
    assert "QUESTION_X" in text

def test_missing_prompt_raises():
    with pytest.raises(FileNotFoundError) : load_prompt("does_not_exist")
