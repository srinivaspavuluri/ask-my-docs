import json
from pathlib import Path

from app.retrieval import search_chunks

GOLD_SET = Path(__file__).resolve().parents[2] / "data" / "eval" / "gold_set.json"


def evaluate_question(q: dict) -> dict:
    chunks = search_chunks(q["question"])
    sources = [chunk["source"] for chunk in chunks]
    top_distance = chunks[0]["distance"] if chunks else None
    question_id = q["id"]
    category = q["category"]
    texts = [chunk["text"].lower() for chunk in chunks]
    chunk_hit = False
    for term in q["must_contain"]:
        for text in texts:
            if term.lower() in text:
                chunk_hit = True

    if q["answerable"]:
        hit = q["expected_source"] in sources
        rank = sources.index(q["expected_source"]) + 1 if hit else None
        return {
            "id" : question_id,
            "category" : category,
            "hit" : hit,
            "chunk_hit" : chunk_hit,
            "rank" : rank,
            "top_distance" : top_distance,
            "sources" : sources
        }
    else:
        correct = len(chunks) == 0
        return {
            "id" : question_id,
            "category" : category,
            "correct_rejection" : correct,
            "top_distance" : top_distance,
            "sources" : sources
        }


def main() -> None:
    questions = json.loads(GOLD_SET.read_text(encoding="utf-8"))["questions"]
    results = [evaluate_question(q) for q in questions]

    for r in results:
        if "hit" in r:
            status = "HIT " if r["hit"] else "MISS"
            chunk_status = "ANSWER" if r["chunk_hit"] else "no-answer"
            print(f"{r['id']} {r['category']:17} {status} {chunk_status:9} rank={r['rank']}  top={r['top_distance']}  {r['sources']}")
        else:
            status = "OK  " if r["correct_rejection"] else "FAIL"
            print(f"{r['id']} {r['category']:17} {status} top={r['top_distance']}  {r['sources']}")

    answerable = [r for r in results if "hit" in r]
    unanswered = [r for r in results if "correct_rejection" in r]
    hits = sum(1 for r in answerable if r["hit"])
    corrects = sum(1 for r in unanswered if r["correct_rejection"])
    chunk_hits = sum(1 for r in answerable if r["chunk_hit"])
    print(f"Runbook hit rate:      {hits}/{len(answerable)}")
    print(f"Answer-chunk hit rate: {chunk_hits}/{len(answerable)}")
    print(f"Rejection rate:        {corrects}/{len(unanswered)}")

    for category in ["exact_identifier", "section", "similar_docs"]:
        in_cat = []
        for r in answerable:
            if r["category"] == category:
                in_cat.append(r)

        cat_hits = 0
        for r in in_cat:
            if r["hit"]:
                cat_hits = cat_hits + 1

        print(f"  {category:17} {cat_hits}/{len(in_cat)}")



if __name__ == "__main__":
    main()