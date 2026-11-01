from app.generation import build_context, clean_citations

def test_context_labels_each_chunk_with_id_and_source():
    chunks = [
        {"chunk_id": 12, "source": "crashloop.md", "text": "Check the pod logs."},
        {"chunk_id": 7,  "source": "ollama.txt",   "text": "Port 11434."},
    ]
    context = build_context(chunks)
    assert "[Chunk 12 | crashloop.md]" in context
    assert "[Chunk 7 | ollama.txt]" in context
    assert context.index("Chunk 12") < context.index("Chunk 7")

def test_clean_citations_removes_duplicates_keeps_order():
    assert clean_citations([15, 13, 15], {13, 15}, False) == [15, 13]

def test_clean_citations_drops_ids_that_were_not_retrieved():
    assert clean_citations([15,99], {15}, False) == [15]

def test_clean_citations_empty_when_refused():
    assert clean_citations([15], {15}, True) == []
