
def build_context(chunks: list[dict]) -> str:
    chunk_parts = []
    for row in chunks:
        chunk_parts.append(f"[Chunk {row['chunk_id']} | {row['source']}]\n" f"{row['text']}")
    context = "\n\n".join(chunk_parts)
    return context
