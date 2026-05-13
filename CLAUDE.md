# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What ReplyRobin Is

A Python pipeline that ingests a user's Gmail inbox, enriches messages with intent + stylometric signals, learns the owner's writing style, and uses a LangGraph multi-agent workflow (planner → drafter → judge) to produce Gmail drafts that mimic that voice. Postgres + `pgvector` stores messages and 1024-dim embeddings; OAuth tokens are stored on disk under `tokens/`.

## Toolchain

- **Python 3.10** (pinned in `.python-version`), managed by **uv**. Install deps with `uv sync`; all run commands go through `uv run`.
- **Postgres with the `pgvector` extension** is required — `Message.embeeding` is a `Vector(1024)` column. Initial DB setup must `CREATE EXTENSION vector;`.
- **Alembic** owns migrations. `alembic/env.py` reads `POSTGRES_CONNECTION` from the environment (`.env`); `alembic.ini` deliberately leaves `sqlalchemy.url` blank so credentials are never committed.

## Common Commands

```bash
# Run the full pipeline (formats, migrates, then runs main.py)
make run

# Format with ruff
make format

# Apply migrations only
make migrate

# Generate a new migration (commented out in Makefile - uncomment when needed)
uv run alembic revision --autogenerate -m "describe change"

# Evaluations (LangSmith dataset + LLM-as-judge)
make eval            # only prints failures
make eval-verbose    # full details + CSV-style DataFrame
make eval-help
```

There is no pytest test suite — quality gates live in `evals/` and are invoked through `python -m evals.eval`.

## Required Environment

See `.env.example`. The codebase reads:

- `POSTGRES_CONNECTION` — full SQLAlchemy URL; consumed by both `db/singleton.py` and `alembic/env.py`.
- `EMAIL_INBOX` — the Gmail account being ingested; also used as the `Org` primary key.
- `GOOGLE_APP_CLIENT_SECRET` — path to the OAuth desktop client JSON (defaults to `./client_secret.json`). First run launches a browser via `InstalledAppFlow.run_local_server(port=3001)` and writes the user token to `tokens/<email>.json`.
- `CUTOFF_DATE` — `YYYY-MM-DD`; threads older than this are skipped during ingest.
- `GEMNI_API_KEY` — **note the typo**, the code reads `GEMNI_API_KEY`, not `GEMINI_API_KEY` (`data_enrichment/processor.py:19`). Used by both extractors and the agents (all default to `gemini-2.5-flash`).
- `LANGSMITH_API_KEY` / `LANGSMITH_TRACING` — used by `@traceable` in the orchestrator and by `langsmith.Client()` in `evals/base_eval.py`.

`tokens/`, `client_secret.json`, and `.env` are gitignored. Do not commit them.

## Architecture

### Cron-style pipeline (`jobs/scheduler.py`)

`main.py` boots the embedding model (`QwenEmbeddingProcess`, `Qwen/Qwen3-Embedding-0.6B`), initializes the engine, then calls `pipe_jobs()`. Three logical jobs that all flow off the `Org` row keyed by `EMAIL_INBOX`:

1. **`fetcher_job`** — `GmailClient.resume_threads_fetch()` walks Gmail thread list using a `nextPageToken` persisted on `Org.page_tokens` (JSONB). Each message is parsed (talon + BeautifulSoup), embedded by `QwenEmbeddingProcess`, then upserted via Postgres `INSERT ... ON CONFLICT`. Initial sync is capped at ~100 threads; subsequent runs resume from the saved page token.
2. **`processor_job`** — `Processor` selects messages whose `signals` column is NULL, runs intent extraction (`IntentExtractor`, batched 20-at-a-time against Gemini with few-shot examples from `data_enrichment/intent_examples.py`), and for messages authored by `org.email` also runs `StyloMetrySignalExtractor`. Output is written back as a JSONB blob on `Message.signals`.
3. **`generate_reply`** — fetches messages where `Thread.message_count == 1` and `sender != org.email`, computes a character profile from aggregated signals (`agent_orchestration/character_profile.py` runs a giant CTE over `message.signals`), pulls 8 semantically similar past messages (`pgvector` cosine distance), invokes the agent workflow, and calls `GmailClient.create_thread_draft` if the workflow returns a draft.

Note: `generate_reply` is currently not wired into `pipe_jobs` (only `fetcher_job` and `processor_job` run). The scheduling loop at the bottom of `scheduler.py` is also commented out — there is no actual cron yet; the pipeline runs once per `make run`.

### Agent workflow (`agent_orchestration/`)

LangGraph `StateGraph` compiled in `master_agent/orchestrator.py`. State is `MultiAgentState` (extends `langgraph.MessagesState`).

```
planner ─┬─▶ drafter ──▶ judge ─┬─▶ drafter   (if weighted_score < 7 and iter < 3)
         │                       └─▶ END
         └─▶ END  (if planner returned no plan or no reference emails)
```

- **`planner_agent`** picks a `draft_plan_selected` and filters `past_emails` down to `reference_emails`. If either is empty, the graph exits with no draft (this is the "spam / not worth replying" path).
- **`drafter_agent`** writes `current_draft` using the character profile + reference emails.
- **`judge_agent`** scores the draft; loop continues until `weighted_score >= APPROVAL_THRESHOLD` (7.0) or `iteration_count >= MAX_ITERATIONS` (3). Both constants live in `agent_orchestration/master_agent/state.py`.

`Worker.run_agent()` (`master_agent/worker.py`) is the single entry point — it compiles the graph once at construction and invokes it per email. The eval harness also goes through `Worker`.

### Data model (`db/schemas.py`)

Three tables, all `org`-scoped by `Org.email` (the PK):

- **`Org`** — owns OAuth identity and `page_tokens` (JSONB list of `{name, last_page_token}`); `get_page_token` / `set_page_token` are mutation helpers.
- **`Thread`** — Gmail thread ID + cached `message_count` + `last_sync`.
- **`Message`** — Gmail message ID, raw body, `signals` JSONB (intent + stylometry), and `embeeding Vector(1024)`. Self-referential `parent_message_id` lets the pipeline reconstruct in-thread ordering.

`StylometrySignalsForMessage` is a *non-mapped* dataclass-style schema describing the shape of `Message.signals` — the column is plain JSONB at the DB level. `CharacterProfile` (SQLModel) is a derived in-memory aggregate, populated by the SQL CTE in `agent_orchestration/character_profile.py`.

Handlers (`db/handlers.py`) consistently use `INSERT ... ON CONFLICT DO UPDATE` for upserts and open a fresh session per call via `get_session_manager()` — there is no long-lived session.

### Evaluation engine (`evals/`)

`BaseEval` is an abstract harness; concrete suites (e.g. `CustomerSupportEval`) implement `get_examples()` and `get_grader_instructions()`. Each example specifies an expected `trajectory` (list of agent names) and `final_draft`.

- Trajectory matching is **subsequence**, not equality: expected `["planner", "drafter"]` passes against actual `["planner", "drafter", "judge"]` (`evaluate_trajectory` in `base_eval.py:65`).
- Draft quality is judged by `gemini-2.5-flash` LLM-as-judge against the expected draft text — but **skipped entirely when `final_draft == ""`** (the spam / no-reply case is judged purely by whether the worker also produced no draft).
- Datasets are pushed to LangSmith via `Client.create_dataset` and re-read on subsequent runs (no overwrite — bump the dataset name to refresh examples).

## Conventions Worth Knowing

- The codebase has consistent typos baked into identifiers: **`embeeding`** (DB column and method names), **`respone_schema.py`** (agent response schemas), **`GEMNI_API_KEY`**. Match them when editing — renaming requires a migration and coordinated changes.
- `print(...)` is the logging pattern throughout — there is no structured logger. The orchestrator uses `logging.info/warning` but nothing configures handlers.
- Engine is created with `echo=True` in `db/singleton.py` — SQL is loud by design during development.
- Gmail OAuth scopes are inconsistent: `local_auth/auth.py` requests `readonly + modify + compose`, but `ingestion_pipeline/gmail_fetcher.py` and `local_auth/manage_secret_file.py` only declare `readonly`. The token granted at first login is what actually counts; if you change scopes you must delete `tokens/<email>.json` to force re-consent.
