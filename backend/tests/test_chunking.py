from app.ingestion import chunk_text

def test_blank_lines_splitting_into_chunk():
    text = "# KubePodCrashLooping\n\n## Meaning\nA pod keeps restarting.\n\n## Mitigation\nCheck the pod logs."
    chunks = chunk_text(text)
    assert len(chunks) == 3
    assert chunks[0] == "# KubePodCrashLooping"

def test_single_new_lines_do_not_split():
    text = "# KubePodCrashLooping\n\n## Meaning\nA pod keeps restarting."
    chunks = chunk_text(text)
    assert len(chunks) == 2
    assert chunks[1] == "## Meaning\nA pod keeps restarting."
    