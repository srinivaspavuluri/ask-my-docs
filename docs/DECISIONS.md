# Ask My Docs — Decision Log

One entry per decision. Format:
**Problem** → **Decision** → **Why not** (the alternative we rejected) → **Recipe** (order of operations, not code) → **Proved by** (the test or check that showed it works).

Phases 0–2 drafted by Claude for review. From Phase 3 on, written by me.

---

## 001 — Separate database, fresh tables
**Problem:** The new app would mix data with the old learning project (`rag-document-ingestion`): documents 1–7, probe leftovers, and deletes affecting both.
**Decision:** A dedicated database `ask_my_docs`, created from `backend/schema.sql`.
**Why not:** New table names in the old database (e.g. `amd_documents`) — one shared backup and password, easy to mix up.
**Recipe:** `createdb` → `psql -f schema.sql` → `\dt` shows 2 tables → `.env` has `DB_NAME=ask_my_docs`.
**Proved by:** `\dt` listed `documents` and `document_chunks`; first document got id 1.

## 002 — Separate venv with CPU-only PyTorch, pinned
**Problem:** The shared `Interview_prep/.venv` hides missing packages ("works on my machine"). Default PyTorch on Linux pulls GPU (CUDA) packages: 4–5 GB.
**Decision:** `backend/.venv` per project; `requirements.txt` starts with `--extra-index-url https://download.pytorch.org/whl/cpu` and `torch==2.14.1+cpu`.
**Why not:** Shared venv — smaller disk use, but packages leak between projects.
**Recipe:** create venv → `pip install torch --index-url .../cpu` → `pip install -r requirements.txt` → `which python uvicorn` must point into `ask_my_docs/backend/.venv`.
**Proved by:** venv dropped to 1.4 GB. `python-multipart` turned out to be missing from this venv while uploads "worked" — the server had been running from the shared venv. Caught and fixed.

## 003 — Project layout: backend/frontend split, `app` package
**Problem:** Netlify publishes one folder; secrets must never be next to it. Imports must work the same way for uvicorn and tests.
**Decision:** `backend/` (never deployed to Netlify) and `frontend/` (the only published folder). Code lives in the `app/` package (empty `__init__.py`); imports are `from app.x import y`. `.env` is read once in `app/config.py`. The embedding model is loaded once in `app/embeddings.py`.
**Why not:** Flat folder — one wrong Netlify setting could publish `.env`.
**Recipe:** always run uvicorn and pytest from `backend/` (`uvicorn app.main:app --reload`, `python -m pytest -v`).
**Proved by:** imports work from `backend/`; from anywhere else: `No module named 'app'`.

## 004 — `/health` design
**Problem:** When something breaks, we need to know at a glance which dependency is down.
**Decision:** `GET /health` checks Postgres (`SELECT 1`) and Ollama (`client.list()`) in **two separate try blocks**. Connections are made per request (lazy), not at startup.
**Why not:** One try block — a dead database would hide Ollama's status. `ollama.chat()` as the check — loads the model, slow.
**Recipe:** `connection = None` → `try: connect, SELECT 1, "ok"` → `except: "error: ..."` → `finally: close if not None` → second try for Ollama → return both.
**Proved by:** 3 tests: both up → ok/ok; Ollama stopped → ok/error; wrong DB password → error/ok and the server still started (lazy connection).
**Open:** raw error text exposes DB user/host — hide it once public (Phase 4).

## 005 — Ingestion: hash first, one transaction
**Problem:** Re-running ingestion created duplicates; a failure halfway could leave a document without its chunks.
**Decision:** SHA-256 of the full content is computed before any DB work. Parent document + all chunks are inserted in **one transaction**, with one `commit()` at the end. Helpers never commit; the caller owns the transaction. `chunk_index` comes from `enumerate`, starting at 0.
**Why not:** Commit per chunk — a crash leaves a partial document. Recalculating the hash with a trigger — the hash should represent the source, not the chunks.
**Recipe:** `content_hash` → connect → check existing → `chunk_text` → `embedding_model.encode(chunks)` (one batch) → `insert_doc` → `insert_chunks` → `commit` · on any error: `rollback`, `raise` · `finally: close`.
**Proved by:** probe test — after a forced `UniqueViolation` and rollback, 0 documents and 0 chunks remained. Note: sequence values are never reused (id 6 was consumed by the rolled-back probe).

## 006 — Replace policy for re-uploads (`UNIQUE(source)`)
**Problem:** The same file uploaded with changed content was stored twice, so old and new versions were both searchable and gave conflicting answers.
**Decision:** One current document per source. `source` = identity ("which document"); `content_hash` = version ("which content").
- new source → insert → `ingested` (201)
- same source, same hash → `skipped` (200)
- same source, different hash → delete old + insert new in one transaction → `replaced` (200)
- concurrent insert of the same new source → `conflict` (409)

`SELECT ... FOR UPDATE` locks the existing row so two simultaneous replaces can't both run.
**Why not:** Versioning (`is_active`) — every retrieval query needs a filter, and the table grows forever. Choose it only if audit or rollback becomes a real requirement.
**Recipe:** `get_existing_document(source)` FOR UPDATE → same hash? return skipped → chunk + embed → if existing: `delete_document` (chunks CASCADE) → `insert_doc ON CONFLICT (source)` → None? rollback, conflict → `insert_chunks` → `commit`.
**Schema change:** `migrations/001_unique_source.sql` (in `BEGIN/COMMIT`). Before adding a UNIQUE constraint, check existing data with `GROUP BY ... HAVING COUNT(*) > 1`. `schema.sql` is kept in sync for fresh setups.
**Proved by:** ollama.txt v1 (id 4) → v2 (id 5, 3 chunks), 1 row for that source, 0 orphan chunks; new source → 201.
**Open:** a replaced document gets a new id, so clients should treat `source` as the stable key. Multi-user later needs `UNIQUE(owner_id, source)`.

## 007 — Upload validation: validate early, fail fast
**Problem:** Wrong, huge, binary or empty files must be rejected before the expensive work (embedding, DB).
**Decision:** Checks in order, the first failure wins:
1. extension in `ALLOWED_EXTENSIONS = {".txt", ".md"}` (via `os.path.splitext(...)[1].lower()`) → 400
2. size ≤ 1 MB → 413
3. `decode("utf-8")` → 400
4. empty content → `content_hash` raises ValueError → 400

Other exceptions are NOT caught (a DB down is an honest 500). The endpoint uses `def`, not `async def`, because ingestion blocks.
**Why not:** Trusting the file name alone — `notes.exe.md` passes the name check; the UTF-8 check is what stops binary content.
**Recipe:** extension → read bytes → size → decode → `ingest_document` (ValueError → 400) → status from `{"ingested": 201, "conflict": 409}.get(status, 200)`.
**Proved by:** 5 validation tests; the `.md` runbook ingested with 201.
**Lesson:** a file containing literal `\n\n` characters (not real newlines) was stored as 1 chunk with no error. Validation can't judge content quality — spot-check stored data.

## 008 — List and delete
**Problem:** On-call needs to see which runbooks are loaded and remove outdated ones.
**Decision:** `GET /documents` — `LEFT JOIN` + `COUNT(c.id)` (documents with 0 chunks still appear), newest first, `created_at.isoformat()`. `DELETE /documents/{id}` — `cursor.rowcount == 1` decides 204 vs 404 in one statement (no SELECT first).
**Why not:** Catching all exceptions and calling them "not found" — hides real failures (same mistake as the old "values already exist" message).
**Recipe:** list: connect → SELECT ... LEFT JOIN ... GROUP BY ... ORDER BY → rows to dicts → close. Delete: DELETE → rowcount → commit → bool → endpoint: `if not deleted: 404` else `Response(204)`.
**Proved by:** list showed 3 newest first; DELETE 1 → 204; again → 404; `abc` → 422 (FastAPI validates the int before the function runs). A committed delete has no undo.

## 009 — Automated tests (pytest)
**Problem:** Manual curl checks are forgotten the next time the code changes.
**Decision:** Start with tests that need no database: hashing, chunking, upload validation (`TestClient`, no uvicorn). Run with `python -m pytest -v` from `backend/`. Every test must be **seen failing once** by breaking the code on purpose.
**Why not:** Tests that write to the real database — they pollute real data.
**Recipe:** file `tests/test_*.py`, function `test_*`, `assert` for values, `pytest.raises(ValueError)` for errors; for endpoints, assert the status code before reading `detail`.
**Proved by:** 9 passing; each group failed when the rule was broken.
**Lesson:** adding `.pdf` to the allowed set made a test **ingest `notes.pdf` into the real database** (201). Validation tests are only DB-safe while validation works → use a separate test database for DB tests.

---

## Known issues / open items
- Importing `app.ingestion` loads the embedding model (~12–15 s per test run) → load it lazily.
- `/health` returns raw error text → hide it once public (Phase 4).
- Placeholder chunker splits on blank lines only; Markdown sections lose their document title ("Mitigation" chunk doesn't mention the alert) → heading-aware chunks with context prefix (Phase 7, measured with evals).
- Embedding runs inside the transaction while the row lock is held → acceptable for now; revisit if uploads get slow.
- `StarletteDeprecationWarning` (httpx → httpx2) in TestClient → revisit when upgrading FastAPI.
