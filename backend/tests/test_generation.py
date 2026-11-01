from app.generation import build_context

def test_context_labels_each_chunk_with_id_and_source():
    chunks = [
        {"chunk_id": 12, "source": "crashloop.md", "text": "Check the pod logs."},
        {"chunk_id": 7,  "source": "ollama.txt",   "text": "Port 11434."},
    ]
    context = build_context(chunks)
    assert "[Chunk 12 | crashloop.md]" in context
    assert "[Chunk 7 | ollama.txt]" in context
    assert context.index("Chunk 12") < context.index("Chunk 7")


