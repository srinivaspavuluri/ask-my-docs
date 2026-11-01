from ollama import Client
from pydantic import BaseModel, ValidationError, Field
from app.config import LLM_MODEL, OLLAMA_HOST

ollama_client = Client(host=OLLAMA_HOST, timeout=90)
REFUSAL = "The runbooks don't contain enough information to answer this."

class GenerationError(Exception):
    """The model returned output we couldn't use."""

class AnswerModel(BaseModel):
    answer : str
    citations : list[int] = Field(max_length=5)
    refused: bool


PROMPT_TEMPLATE = """You are an on-call assistant. Answer ONLY from the runbook context below.

Rules:
- Use only facts stated in the context. No outside knowledge.
- In "citations", list the chunk IDs (the numbers after "Chunk") that support your answer.
- If the context does not contain the answer, set "refused" to true, "citations" to [],
  and "answer" to exactly: "{refusal}"

Context:
{context}

Question: {question}
"""


def build_context(chunks: list[dict]) -> str:
    chunk_parts = []
    for row in chunks:
        chunk_parts.append(f"[Chunk {row['chunk_id']} | {row['source']}]\n" f"{row['text']}")
    context = "\n\n".join(chunk_parts)
    return context

def clean_citations(raw: list[int], allowed_ids: set[int], refused: bool) -> list[int]:
    if refused:
        return []
    citations = [c for c in raw if c in allowed_ids]
    citations = list(dict.fromkeys(citations))
    return citations


def generate_answer(question: str, chunks: list[dict]) -> dict:
    context = build_context(chunks)
    prompt = PROMPT_TEMPLATE.format(refusal=REFUSAL, context=context, question=question)
    response = ollama_client.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role" : "user",
                "content" : prompt
            }
        ],
        format=AnswerModel.model_json_schema(),
        options={
            "temperature" : 0,
            "num_predict": 300,
            "repeat_penalty": 1.2
        }
    )

    try:
        parsed_answer = AnswerModel.model_validate_json(response["message"]["content"])
    except ValidationError as e:
        raise GenerationError("The model returned invalid output.") from e

    allowed_ids = {chunk["chunk_id"] for chunk in chunks}
    citations = clean_citations(parsed_answer.citations, allowed_ids, parsed_answer.refused)
    
    return {
        "answer" : REFUSAL if parsed_answer.refused else parsed_answer.answer,
        "citations" : citations,
        "refused" : parsed_answer.refused
    }

