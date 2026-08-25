# Session history: greenfield semantic review

Captured: 2026-08-24T22:25:06.213-07:00

## Goal
Review all tracked and untracked greenfield `llm-expert-system` workspace changes by behavior, excluding generated validation workspaces, and produce a severity-ranked semantic review covering correctness, security, lifecycle, routing, interfaces, deployment, CI, installers, frontend, provenance, and abstention.

## Work completed
- Inventoried local changes against `main`, including untracked files.
- Reconstructed ingestion, provider, IR, renderer, worker, routing, conflict, lifecycle, storage, API/CLI, React, Docker/Compose, installer, and CI behavior.
- Reproduced three blocking lifecycle defects: matching drafts remain inactive, both conflict sides can be accepted as resolved, and invalid Clingo IR can receive a passing active manifest.
- Wrote the review, re-read it from disk, applied the required editing pass, and added a 19-item issue index.

## Key decisions/debugging
- Treated generated/ignored validation workspaces as out of scope.
- Used `main` as the base branch; most implementation files are untracked, so status inventory and direct file reads supplemented `git diff main`.
- Assigned `NEEDS_CHANGES`; no PR comments were posted.
- Distinguished the Prolog term-injection concern as likely rather than confirmed; all other findings were directly traced or reproduced.

## Files changed
- `semantic-review/2026-08-24-220636-pr-local.md` — complete edited semantic review.
- `session_history/2026-08-24-greenfield-semantic-review.md` — this bookkeeping record.
- `web/node_modules/` was populated/partially populated by validation attempts and remains ignored; no product source was modified.

## Validation
- `uv run ruff check src tests` — passed.
- `uv run mypy src` — passed.
- `uv run pytest --cov --cov-report=term-missing` — 20 passed, 77% coverage, one Starlette/httpx deprecation warning.
- `npm test` — passed (one contract test).
- `npm ci --ignore-scripts` — blocked twice by local `UNABLE_TO_VERIFY_LEAF_SIGNATURE`; local TypeScript lint/build therefore could not run from a clean install.
- Docker runtime image build — passed, including cached frontend build.
- `docker compose config --quiet` with a supplied token — passed; without the required token it correctly failed interpolation.
- Runtime image import smoke test with a token — passed.
- Review issue-index count — 19; review file exists.

## Model usage
Exact per-model token totals: Not exposed by Kiro; exact total unavailable.

Model invocation counts: unavailable for this conversation. The workspace has no matching Kiro `workspace-sessions/.../sessions.json` index, the required `scripts/collect-kiro-session.ps1` is absent, and the newest local `Kiro Logs.log` files contained no matching `[q-developer-converse] Sending GenerateAssistantResponse` events that could be safely correlated. No model identity or call count was inferred.

## Visible-text token estimate
Unavailable: no linked Kiro session JSON for this workspace/conversation was found, so recoverable user/assistant message text could not be measured without fabricating evidence. Hidden system instructions, tool schemas/results, cache traffic, compaction data, and omitted assistant output are not estimated.

## Wall-clock duration
Active-session duration: unavailable because no matching indexed session with `dateCreated` was found.

Conversation-chain duration: unavailable because no linked conversation ID or exact first logged model event could be correlated. Capture time is recorded above.

## Metadata method/limitations
The prescribed collector script was searched for and not found. Kiro's `%APPDATA%` workspace-session indexes were inspected for the resolved workspace, and the newest three Kiro agent logs were checked only for exact model-send events. No current-session match was available, so token totals, visible-text estimates, model counts, and duration are explicitly left unavailable rather than estimated.

## Follow-up status
Review complete. Nineteen actionable findings remain; verdict is `NEEDS_CHANGES`. No implementation fixes or commits were requested or made.

## Conversation-chain continuation: AI-only contribution policy

Captured: 2026-08-24T23:10:04.0145223-07:00

### Goal
Add repository-wide instructions for future AI coding agents, prohibit direct human file editing, retain human governance and review, require the normal protected-branch pull-request flow, validate the documentation, and commit/push only this policy change without mixing the existing uncommitted implementation work.

### Work completed
- Created `AGENTS.md` with repository purpose, architecture map, trust boundaries, coding conventions, dependency/generated-file rules, validation commands, Git safety, and definition of done.
- Created `CONTRIBUTING.md` with an explicit ban on direct human editing, permitted human governance/review actions, mandatory AI-agent authorship, and the standard issue/branch/PR/review/checks/merge workflow.
- Added contribution links to the working README.
- Preserved the extensive pre-existing working tree by staging only a baseline-relative README policy hunk rather than the unrelated README rewrite.
- Created branch `docs/ai-agent-contribution-policy` before commit/push operations.

### Validation status
- Targeted `git diff --check -- AGENTS.md CONTRIBUTING.md README.md` passed.
- Local relative-link validation for `AGENTS.md`, `CONTRIBUTING.md`, and `README.md` passed.
- Text inspection confirmed that `CONTRIBUTING.md` explicitly prohibits direct human editing and requires normal pull-request review and merge.
- No application tests were run because this continuation changes documentation policy only.

### Model-call evidence and duration
- Current model identity exposed by the session: GPT 5.6 Sol.
- Exact per-model token totals and exact model invocation counts are not exposed by Kiro in the available session context, so they are not recorded or estimated.
- Exact conversation-chain duration is unavailable. The capture timestamp above is authoritative; no start timestamp tied to a Kiro conversation UUID was exposed.

### Bookkeeping limitations
The available workspace history record does not contain a Kiro conversation UUID, and no session-history collector skill or current-session UUID is exposed in this environment. This existing conversation-chain record was reused rather than creating a duplicate file. No token counts, invocation totals, UUID, or duration were fabricated.

## Conversation-chain continuation: greenfield implementation commit

Captured: 2026-08-24T23:23:03.3223215-07:00

### Goal and commit scope
At the user's explicit request, validate and commit/push the remaining greenfield implementation on `docs/ai-agent-contribution-policy`. The intended commit includes backend source/tests, React source and npm lockfile, examples, generated schemas, installers, Docker/Compose, CI, architecture/security/README documentation, the semantic review, and this required session-history record. Local virtual environments, caches, coverage data, frontend build/dependency output, and local expert-system/evaluation/acceptance workspaces are excluded.

### Completed work
- Inventoried all tracked and untracked files and separated product artifacts from local/generated runtime state.
- Regenerated the three public JSON Schemas after the pending model changes.
- Updated `.gitignore` and `.dockerignore` for suffixed evaluation/acceptance workspaces.
- Corrected README and architecture/security documentation that overstated internal networking, no-egress behavior, hard timeout termination, filesystem immutability, native activation certification, authenticated React support, and completed optimization/cross-engine composition.
- Retained the semantic review with its `NEEDS_CHANGES` findings so known limitations remain explicit rather than hidden by the commit.

### Final validation evidence
- `uv run ruff check src tests` — passed.
- `uv run mypy src` — passed with no issues in 16 source files.
- `uv run pytest --cov --cov-report=term-missing` — 20 passed, 76% total coverage; one existing Starlette/httpx deprecation warning.
- `npm test --prefix web` — one contract test passed.
- Host `npm run lint --prefix web` — not runnable because the local ignored `web/node_modules` lacks `tsc`; this is an environment/dependency-install limitation, not reported as passed.
- `docker build --target web-builder -t llm-expert-system-web:commit-validation .` — passed and validated the locked TypeScript/Vite build.
- PowerShell parser checks for installer/acceptance scripts — passed.
- `bash -n` for Linux installer/acceptance scripts — passed.
- Tokenized `docker compose config --quiet` — passed.
- Evaluation against `examples/family` — passed with 100% provenance coverage; host Prolog remained unavailable while CLIPS, Z3, and Clingo were healthy.
- Runtime Docker image build — passed.
- Runtime image diagnostics — SWI-Prolog, CLIPS, Z3, and Clingo all available.
- Schema export and JSON parsing — three valid generated schema files.
- Documentation relative-link validation — passed.
- `git diff --check` — passed.

### Known limitations
The committed semantic review documents unresolved product limitations. In particular, the current implementation does not yet provide full native activation certification, hard process-kill timeouts, per-engine container isolation/no-egress, goal-specific semantics for every non-Prolog engine, or a secure runtime token-entry flow in the production React bundle. Documentation now states these boundaries directly.

### Model-call evidence and duration
- Current model identity exposed by the session: GPT 5.6 Sol.
- Exact per-model token totals and exact model invocation counts are not exposed in the available Kiro context; none are estimated.
- Exact conversation-chain and active-task durations are unavailable because no Kiro conversation UUID/start timestamp is exposed. The capture timestamp above is authoritative.

### Bookkeeping limitations
The existing conversation-chain record is reused because no collector skill, collector script, session UUID, or model accounting API is available in this environment. Token counts, invocation totals, UUID, and durations were not fabricated.