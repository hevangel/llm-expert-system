# LLM Expert System

A local-first framework that turns Markdown, text, JSON, and YAML into versioned, provenance-aware expert systems for **SWI-Prolog, CLIPS, Z3, and Clingo**. An LLM proposes typed knowledge; deterministic host policy schema-validates the IR and renders engine artifacts. Raw model-generated code is never executed.

> The original repository name used `llm-experty-system`; the distribution, import package, API title, and container use the corrected canonical name `llm-expert-system` / `llm_expert_system`.

## What it provides

- Strict Pydantic knowledge IR for sources, evidence, entities, facts, rules, constraints, goals, conflicts, routing, and reasoning results.
- Source hashes and line/structural provenance for `.md`, `.txt`, `.json`, `.yaml`, and `.yml`.
- Deterministic fake provider for CI/examples plus an optional LiteLLM adapter for hosted, local, and OpenAI-compatible models.
- Safe deterministic renderers producing `.pl`, `.clp`, `.smt2`, and `.lp` artifacts.
- Authenticated SWI-Prolog MQI sessions and native clipspy, Z3Py, and Clingo adapters behind a request broker.
- Capability routing: relational → Prolog, forward chaining → CLIPS, constraints → Z3, planning/non-monotonic reasoning → Clingo. Optimization and cross-engine composition remain future work.
- Conservative contradiction handling: affected goals abstain until changed evidence or an audited explicit resolution.
- SQLite metadata, versioned artifact directories, validation reports, atomic active-version pointers, and rollback.
- Typer CLI, FastAPI, and React workflows over the shared service.
- Pinned Python/npm lockfiles, Windows/Linux installers, Docker/Compose, CI, evaluation fixtures, and acceptance scripts.

## Quick start

Requirements: Python 3.11–3.13, `uv`, Node.js, npm, and SWI-Prolog. CLIPS, Z3, and Clingo are installed from pinned Python wheels.

```powershell
# Windows; add -InstallPrerequisites to use winget for missing tools
.\scripts\install.ps1

# Generate and activate a deterministic example
uv run llm-expert generate examples/family --workspace .llm-expert --json
uv run llm-expert versions --workspace .llm-expert --json
uv run llm-expert diagnostics --workspace .llm-expert --json

# Run the API manually (long-running)
uv run llm-expert serve --workspace .llm-expert
```

```bash
# Linux; add --install-prerequisites for supported apt/dnf systems
./scripts/install.sh
uv run llm-expert generate examples/family --workspace .llm-expert --json
uv run llm-expert serve --workspace .llm-expert
```

The web application is built by the installers. For frontend development, run `npm run dev` manually from `web/`; it proxies API traffic to `127.0.0.1:8000`.

## Provider configuration

The default `fake` provider recognizes deterministic example statements such as `Alice is parent of Bob.`, `fact: predicate(value)`, and `fact: !predicate(value)`. It needs no network or credentials.

Copy `.env.example` to `.env` and set these values for a real provider:

```dotenv
LLM_EXPERT_PROVIDER=litellm
LLM_EXPERT_MODEL=openai/your-model
# Set the provider-specific API key only in the environment or ignored .env file.
```

Install provider support with `uv sync --frozen --extra llm --extra engines`. Provider output must satisfy the canonical JSON Schema. Document text is delimited as untrusted data and cannot introduce tools, scripts, engine directives, or arbitrary source code.

## CLI

```text
llm-expert health [--json]
llm-expert init --workspace PATH
llm-expert diagnostics --workspace PATH [--json]
llm-expert generate SOURCE --workspace PATH [--activate|--no-activate] [--json]
llm-expert versions --workspace PATH [--json]
llm-expert conflicts --workspace PATH [--json]
llm-expert resolve-conflict ID --accept ITEM --note TEXT --workspace PATH
llm-expert query PREDICATE [ARGUMENTS...] --capability CAPABILITY --workspace PATH [--json]
llm-expert rollback VERSION --workspace PATH
llm-expert export VERSION DESTINATION --workspace PATH
llm-expert export-schema --destination schemas
llm-expert serve --host 127.0.0.1 --port 8000 --workspace PATH
```

Query exit code `3` means conservative abstention; code `2` means an execution error or timeout.

## API and web

OpenAPI is available at `/docs`. Principal v1 routes are:

- `POST /api/v1/generate`
- `GET /api/v1/versions`
- `GET /api/v1/versions/{id}/knowledge`
- `GET /api/v1/conflicts`
- `POST /api/v1/conflicts/{id}/resolve`
- `POST /api/v1/query`
- `POST /api/v1/rollback`
- `GET /health` and `GET /ready`

Loopback development may run without a token. `LLM_EXPERT_API_TOKEN` is mandatory when binding beyond loopback and protects `/api/v1/*`; `/health`, `/ready`, and static assets are currently public. Send the token as `Authorization: Bearer <token>`. The React interface displays engine readiness, generation, querying, route/result details, conflicts, history, and rollback during tokenless loopback development. The production static bundle does not yet provide a secure runtime operator-token entry flow, so authenticated deployments should use the CLI/API until that flow is implemented.

## Knowledge lifecycle

```text
Draft → IR validated → Rendered → Syntax checked → Semantic checked
      → Consistency checked → Staged → Active → Superseded
```

The state labels are persisted for auditability, but the current activation path fully enforces only typed IR/evidence parsing and deterministic renderer completion; native syntax/semantic certification is not yet complete. Failed rendering becomes rejected and cannot replace the last-known-good version. The registry stops writing finalized directories, but filesystem permissions do not make them tamper-proof and checksums are not yet reverified before every query. Activation and rollback update a singleton SQLite pointer transactionally.

## Docker

The image uses digest-pinned Python and Node bases, a multi-stage frontend/backend build, a non-root UID, a health check, and all four engines. Compose additionally applies a read-only root filesystem, dropped capabilities, `no-new-privileges`, bounded PIDs/memory/CPU, a temporary `/tmp`, and persistent `/data`. The API, provider, and engines share one container and an egress-capable bridge network; this is defense in depth, not per-engine isolation.

```powershell
$env:LLM_EXPERT_API_TOKEN = "replace-with-a-long-random-token"
docker compose build
docker compose up
```

Visit `http://127.0.0.1:8000`. Hosted-provider calls use the same bridge egress as the engine process. Deploy separate least-privilege engine workers and explicit network controls before treating engine execution as no-egress isolation.

## Validation and evaluation

```powershell
uv run ruff check src tests
uv run mypy src
uv run pytest --cov
uv run python -m llm_expert_system.evaluation examples/family
npm test --prefix web
npm run lint --prefix web
npm run build --prefix web
.\scripts\acceptance.ps1
```

The bundled domains cover family relations, equipment observations, scheduling, non-monotonic planning, contradictions, and a hybrid maintenance scenario. Native SWI-Prolog diagnostics require the `swipl` executable; the Python package alone is only the MQI client.

## Security and extension guidance

See [security boundaries](docs/security.md) and [architecture](docs/architecture.md) before adding IR nodes, providers, renderers, or engine functions. Restricted local mode reduces risk but is not a complete OS sandbox; use container isolation for untrusted datasets. Never add an escape hatch that evaluates LLM-authored Python/shell or accepts raw engine programs as provider output.

## Contributing

All repository file changes must be authored by an AI coding agent and submitted through the normal branch and pull-request flow. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the mandatory policy; coding agents must also follow [AGENTS.md](AGENTS.md).

## Background and sources

No canonical Karpathy repository explicitly named “LLM wiki” was identified. This project interprets the idea as iterative source ingestion, structured synthesis, provenance-aware generation, and regeneration when sources change; it does not claim compatibility with a specific implementation.

Integration and security decisions draw on the official [SWI-Prolog MQI](https://www.swi-prolog.org/pldoc/man?section=mqi), [Prolog MQI Python guidance](https://www.swi-prolog.org/packages/mqi/prologmqi.html), [clipspy documentation](https://clipspy.readthedocs.io/en/latest/), [Z3Py API](https://z3prover.github.io/api/html/namespacez3py.html), [Clingo Python API](https://potassco.org/clingo/python-api/current/clingo/), [LiteLLM structured outputs](https://docs.litellm.ai/docs/completion/json_mode), [FastAPI security guidance](https://fastapi.tiangolo.com/tutorial/security/), [Docker build practices](https://docs.docker.com/build/building/best-practices/), and the [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/).

Content informed by these sources was paraphrased for compliance with licensing restrictions.

## License

MIT © 2026 hevangel. See [LICENSE](LICENSE).
