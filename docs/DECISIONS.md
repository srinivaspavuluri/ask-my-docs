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

## 010 — Retrieval threshold vs chunk context

**Problem:** For "How do I fix KubePodCrashLooping?", only chunk 0 (the title, no fix) was returned. The fix (chunk 2, "## Mitigation") was cut by the 0.5 threshold at 0.554, because it doesn't contain the alert name: chunking separated the subject from its answer. Same for Ollama: "It exposes... port 11434" = 0.521, cut.

**Decision:** Keep the threshold at 0.5 for now. In Phase 7, add the document name and section to the front of each chunk ("crashloop.md > Mitigation: ...") so the answer chunk contains its subject. Measure with the Phase 3b evals: baseline now, compare after. Keep it only if the numbers improve.

**Why not:** Raising the threshold (e.g. 0.6). It changes every query: more chunks pass, including ones that shouldn't (similar wording from other runbooks), and this gets worse as the corpus grows. It would also be tuned on just 2 questions, and it hides the cause instead of fixing it: the answer chunk still lacks its subject.

**Recipe:** embed the question (384 numbers) → compare with every chunk's embedding using `<=>` (cosine distance, lower = more similar) → `WHERE` keeps only distance ≤ 0.5 → `ORDER BY distance` (closest first) → `LIMIT top_k` (a maximum: can return fewer, and doesn't guarantee the right chunks) → `JOIN documents` to get `source` for citations. The embedding is passed twice: once for the distance column, once for the `WHERE`.

**Proved by:** Normal settings (top_k 2, threshold 0.5): Kube → only chunk 0 (0.215); Ollama → only chunk 0 (0.405). Loosened (top_k 10, threshold 1.0): the answer chunks ranked 2nd — Kube Mitigation 0.554, Ollama port 0.521. So the ranking is right; the threshold alone cut them. France → `[]` (correct rejection).

**Also found:** crashloop.md chunks show `'\\n'` in repr, meaning a literal backslash + n is stored, not a real line break. This adds junk to the embedding. Fix: correct the file and upload it again (replace policy → "replaced").

## 011 — Structured JSON output from the LLM

**Problem:** We need citations that code can check, so the model must return JSON (`{answer, citations, refused}`) instead of free text. With forced JSON (`format=` schema), the Kube question looped inside `citations` (`15, 13, 14, 15, 13, 14...`) until the 300-token limit cut it off → invalid JSON → crash after 1m31s.

**Decision:** Keep JSON, but contain the failure: `Field(max_length=5)` on citations (the schema forces the list to close), `repeat_penalty: 1.2` (stops the loop at the source), `clean_citations()` (drops ids that weren't retrieved, removes duplicates, keeps order, empty when refused), `GenerationError` when output still doesn't parse, and limits on every model call (`timeout=90`, `num_predict=300`).

**Why not:** Free text — it worked (10 s, correct answer) but citations would be words in a sentence that code can't reliably check.

**Recipe:** build context with `[Chunk id | source]` labels → prompt with rules → `ollama_client.chat(format=AnswerModel schema, temperature 0, num_predict 300, repeat_penalty 1.2)` → parse with Pydantic (fail → `GenerationError`) → `clean_citations(raw, allowed_ids, refused)` → return the dict.

**Proved by:** Same question and chunks without `format=` → clean answer in 10 s, so forced JSON was the trigger, not the data. With `max_length=5` → valid JSON but repeated ids `[15, 13, 14, 15, 13]`. With `repeat_penalty` → `[13, 15]` in 24 s. `clean_citations` tests: duplicates removed, invented ids dropped, empty when refused. With the right chunk in context, the Ollama question answered "11434" citing only chunk 9; with the wrong chunks, it refused.

**Open:** `repeat_penalty` changed the alert name in the answer ("kubepodcrashloop"). Check exact identifiers in the Phase 3b evals before keeping it.

## 012 — `POST /ask` endpoint

**Problem:** Search, context and generation existed separately; nothing answered a question end to end. Failures from different layers (bad question, bad model output, slow model) needed different responses. When the model refused, it wrote `"refused"` instead of the exact refusal sentence, because `repeat_penalty` penalizes words that already appear in the prompt.

**Decision:** `POST /ask` with a JSON body (`AskRequest`). Refuse **before** the LLM when retrieval returns nothing (fast, free, can't make anything up). Status codes per layer: `ValueError` → 400, `GenerationError` → 502, `httpx.TimeoutException` → 504, anything else → 500. Return `sources` (only the cited chunks) so the frontend can show the evidence. When `refused` is true, the code sets the answer to `REFUSAL` instead of trusting the model's wording.

**Why not:** `GET /ask?q=` — questions can be long and end up in URLs, history and logs. Calling the LLM with an empty context — the model would answer from its own memory.

**Recipe:** validate → `search_chunks` → no chunks? return refusal → `generate_answer` → map errors to 400/502/504 → `sources` = retrieved chunks whose id is in `citations` → return `{**result, "sources": sources}`.

**Proved by:** Ollama port question (only chunk 8 retrieved) → refused with the full sentence, both before and after the fix. Empty question → 400 (test). 15 tests passing.

**Open:** the app refuses questions it should answer (port, Kube fix) because of the retrieval gap in 010. Phase 3b evals will measure how often.

## 013 — Prompt as a versioned file

**Problem:** The prompt was a string inside `generation.py`. Any edit silently changed behavior, there was no record of which prompt produced which answer, and eval results from before and after an edit couldn't be compared.

**Decision:** Each prompt version is a separate file in `backend/prompts/` (`answer_v1.txt`) that is never edited after use; a change means a new file (`answer_v2.txt`). `PROMPT_VERSION` in `.env` picks the active one (default `answer_v1`). `app/prompts.py` loads it once at import, so a missing file stops the app at startup instead of failing on the first `/ask`. `generate_answer` returns `prompt_version`, which will be logged with every request (3.4).

**Why not:** Keeping the prompt in code — no history, and editing it means editing code. Reading the file on every request — slower, and a missing file would only show up when a user asks a question.

**Recipe:** `load_prompt(version)` → `PROMPTS_DIR / f"{version}.txt"` → missing → `FileNotFoundError` → `read_text` → `PROMPT_TEMPLATE.format(refusal=..., context=..., question=...)`. Literal braces in a future prompt must be doubled (`{{ }}`).

**Proved by:** Editing the file changed the loaded text (the file is really used; the old hard-coded string had been overwriting it until removed). Tests: all three placeholders present, formatting fills them (using unique markers), missing version raises. Behavior of `/ask` unchanged: refactor only; 18 tests passing.

**Lesson:** `assert "a" and "b" in x` only checks `"b"`; write one `assert` per fact. Test values must be unique markers (`"C"` matched "Context" in the prompt itself).

---

## Known issues / open items
- Importing `app.ingestion` loads the embedding model (~12–15 s per test run) → load it lazily.
- `/health` returns raw error text → hide it once public (Phase 4).
- Placeholder chunker splits on blank lines only; Markdown sections lose their document title ("Mitigation" chunk doesn't mention the alert) → heading-aware chunks with context prefix (Phase 7, measured with evals).
- Embedding runs inside the transaction while the row lock is held → acceptable for now; revisit if uploads get slow.
- `StarletteDeprecationWarning` (httpx → httpx2) in TestClient → revisit when upgrading FastAPI.
