from pathlib import Path
from app.ingestion import ingest_document

CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "runbooks"


def main() -> None:
    counts = {}
    for path in sorted(CORPUS_DIR.rglob("*.md")):
        source = path.relative_to(CORPUS_DIR).as_posix()
        content = path.read_text(encoding="utf-8")
        result = ingest_document(source=source, title=path.stem, content=content)
        print(f"{result['status']:9} {result['chunks']:3} chunks  {source}")
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    print(counts)


if __name__ == "__main__":
    main()
