# Ask My Docs — On-call Runbook Assistant

Ask a question during an incident and get an answer grounded in your team's runbooks, with citations to the exact runbook it came from. Everything runs on local models (Ollama + PostgreSQL/pgvector), so internal documents never leave the machine and each question costs nothing.

> **Data note:** the corpus is 10 public [Prometheus Operator runbooks](https://github.com/prometheus-operator/runbooks) (Apache-2.0) plus 3 runbooks for `payments-api`, a **fictional** service written to simulate internal docs. No real company data is used.

## How it works

```text
Upload (.txt / .md)                     Question
      │                                     │
      ▼                                     ▼
hash → skip if unchanged             embed question (all-MiniLM-L6-v2)
      │                                     │
chunk → embed → PostgreSQL ◄──── pgvector search (cosine distance ≤ 0.5, top 2)
                (pgvector)                  │
                                     no chunks? → refuse (LLM not called)
                                            │
                                     phi4-mini (Ollama) → JSON {answer, citations, refused}
                                            │
                                     citations checked against retrieved chunks
                                            │
                                     every request logged in query_logs
```

## Current status

| Phase | What | Status |
|---|---|---|
| 0–1 | Project setup, health check, document upload + ingestion | ✅ |
| 2 | Re-upload replaces the old version, list/delete documents, `.md` support | ✅ |
| 3 | `/search`, `/ask` with structured JSON answers, versioned prompt, request logging | ✅ |
| 3b | Runbook corpus, 20-question gold set, retrieval eval | ✅ |
| 3b | Answer eval + model comparison | 🚧 in progress |
| 4–8 | Security (API key, CORS), web frontend, public access, better chunking, online hosting | ⬜ planned |

## Latest evaluation (baseline)

Retrieval only, 20 questions (15 answerable, 5 not answerable from the runbooks):

| Metric | Result |
|---|---|
| Right runbook retrieved | **14 / 15** |
| Chunk containing the answer retrieved | **3 / 15** |
| Unanswerable questions correctly rejected | **5 / 5** |

**What this shows:** retrieval almost always finds the right runbook, but rarely the part with the answer. Two causes: headings end up in chunks of their own, separated from their text, and questions describe *symptoms* while the answer sits in a different section of the runbook. Improving chunking is the next major step, measured against these numbers.

Design decisions, alternatives and evidence for every step are in **[docs/DECISIONS.md](docs/DECISIONS.md)**.

## Tech stack

Python 3.12 · FastAPI · PostgreSQL + pgvector · sentence-transformers (`all-MiniLM-L6-v2`, CPU) · Ollama (`phi4-mini`) · pytest

## Setup

### Prerequisites

- Python 3.12
- PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension available
- [Ollama](https://ollama.com), with the model pulled: `ollama pull phi4-mini`

### 1. Database

```bash
createdb -h localhost -U postgres ask_my_docs
psql -h localhost -U postgres -d ask_my_docs -f backend/schema.sql
```

`schema.sql` always describes the **current** schema, so a new database needs only this file. The files in `backend/migrations/` are for upgrading an **existing** database, applied in order (001, 002, 003); don't run them on a database created from `schema.sql`.

### 2. Python environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` installs the CPU-only build of PyTorch (about 1.4 GB in total instead of 4–5 GB with the GPU build).

### 3. Configuration

```bash
cp .env.example .env
```

Fill in `DB_USER` and `DB_PASSWORD`. The other values have working defaults:

| Variable | Default | Meaning |
|---|---|---|
| `LLM_MODEL` | `phi4-mini` | Ollama model used to write answers |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Model used to embed chunks and questions |
| `RAG_THRESHOLD` | `0.5` | Maximum cosine distance for a chunk to count as relevant |
| `RAG_TOP_K` | `2` | Maximum chunks passed to the model |
| `PROMPT_VERSION` | `answer_v1` | Which file in `backend/prompts/` is used |

### 4. Load the runbooks

```bash
python -m scripts.load_corpus
```

Safe to run again: unchanged files are skipped.

### 5. Run

```bash
uvicorn app.main:app --reload
```

Run all commands from the `backend/` folder. API docs: <http://localhost:8000/docs>

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Checks the database and Ollama separately |
| `POST` | `/documents` | Upload a `.txt` / `.md` file (201 new, 200 replaced or unchanged) |
| `GET` | `/documents` | List documents with chunk counts |
| `DELETE` | `/documents/{id}` | Delete a document and its chunks (204 / 404) |
| `GET` | `/search?q=...` | Retrieval only: the matching chunks, no LLM |
| `POST` | `/ask` | Grounded answer: `{"answer", "citations", "refused", "sources"}` |

Example:

```bash
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Checkout returns 502s right after a deploy. How do I undo it?"}'
```

Every `/ask` response has an `X-Request-ID` header that matches its row in the `query_logs` table.

## Tests and evaluation

```bash
python -m pytest -v               # unit and API tests (no LLM needed)
python -m scripts.eval_retrieval  # retrieval scores on data/eval/gold_set.json
```

## Project layout

```text
backend/
  app/          FastAPI application (ingestion, retrieval, generation, logging)
  prompts/      versioned prompt files (answer_v1.txt)
  migrations/   schema changes for existing databases
  scripts/      corpus loader and evaluation scripts
  tests/        pytest tests
data/
  runbooks/     prometheus/ (public, Apache-2.0) and custom/ (fictional payments-api)
  eval/         gold_set.json — 20 questions with expected runbook, section and answer terms
docs/
  DECISIONS.md  decision log: problem, decision, alternatives, evidence
frontend/       web page (planned)
```
