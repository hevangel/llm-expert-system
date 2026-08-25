# Contributing

## AI-agent-only authorship policy

Direct human editing of this repository is prohibited. All changes to source code, tests, documentation, examples, schemas, scripts, workflows, dependency declarations, lockfiles, and configuration must be authored and applied by an AI coding agent operating in the contributor's checkout.

Humans remain responsible for intent and governance. Humans may:

- open or refine issues;
- provide requirements, constraints, and acceptance criteria to an AI coding agent;
- review plans, diffs, test evidence, security impact, and generated artifacts;
- request revisions from the agent;
- approve or reject pull requests; and
- merge an approved pull request through the repository's normal protected-branch flow.

Humans must not directly type, paste, patch, format, or otherwise modify repository files. This includes “small” fixes, conflict resolutions, generated files, dependency updates, and edits made in a web UI. If a direct human edit occurs, do not continue from it: revert that edit and have an AI coding agent recreate the intended change with validation and provenance in the pull request.

Using an AI agent does not transfer accountability. The contributor and reviewers are responsible for ensuring the resulting change is correct, secure, licensed appropriately, and consistent with project policy.

## Normal pull-request flow

All contributions use the standard issue/branch/pull-request/review workflow. AI-only authorship does not permit direct pushes or bypass normal review.

1. **Describe the change.** Open or reference an issue for non-trivial work. State the problem, desired behavior, constraints, security implications, and acceptance criteria.
2. **Create a branch.** Branch from an up-to-date default branch using a descriptive name such as `feat/...`, `fix/...`, `docs/...`, or `chore/...`. Never make changes directly on `main` or `master`.
3. **Delegate implementation.** Give the issue and relevant repository context to an AI coding agent. The agent must read and follow [AGENTS.md](AGENTS.md), inspect existing code before editing, and preserve unrelated work.
4. **Review the agent's plan and changes.** Humans may direct or reject the approach, but all file revisions must still be made by the agent.
5. **Validate.** The agent runs the checks required by `AGENTS.md` and records exact commands, outcomes, warnings, and environmental limitations. Behavior changes require appropriate tests; safety controls must not be weakened to obtain a passing result.
6. **Commit and push through the agent.** When explicitly authorized, the agent stages only intended files, creates focused non-amended commits, and pushes the branch without force.
7. **Open a pull request.** Use a concise title and include the required information below. Draft pull requests are encouraged for early design or security review.
8. **Review normally.** At least one human reviewer examines the complete diff and validation evidence. Review comments and requested changes are implemented by an AI coding agent on the same branch.
9. **Pass required checks.** Do not bypass hooks, branch protection, CI, required reviews, security checks, or merge restrictions.
10. **Merge normally.** A human maintainer merges the approved pull request using an allowed repository merge method. Direct pushes to the protected default branch and force pushes are prohibited.

## Pull-request requirements

Every pull request must include:

- **Problem:** what was wrong or missing.
- **Approach:** the design and why it fits the existing architecture.
- **AI authorship:** the agent/tool used for every repository file change. Do not include secrets, private prompts, or proprietary source documents.
- **Files and behavior:** the important changed areas and user-visible effects.
- **Security and provenance:** effects on trust boundaries, source ingestion, evidence, authentication, engine execution, conflicts, resource limits, dependencies, and deployment. Write “none” only after checking each relevant boundary.
- **Validation:** exact commands and results, including skipped or unavailable checks.
- **Compatibility and migration:** schema, API, CLI, workspace, database, configuration, or deployment impact.
- **Limitations and follow-ups:** known gaps that are intentionally outside scope.

A pull request is not ready when it contains unexplained generated changes, unrelated formatting, secrets, proprietary input data, failing required checks, fabricated validation, unresolved high-severity findings, or behavior that exceeds its documented security guarantees.

## Development standards

### Preserve the trusted generation boundary

Providers return strict typed IR only. Deterministic host code validates provenance and renders engine artifacts. Never introduce execution of model-authored Python, shell, raw Prolog, CLIPS, SMT-LIB, Clingo, directives, callbacks, tools, or arbitrary file paths.

Changes involving ingestion, providers, IR, conflicts, rendering, native engines, lifecycle, storage, routing, authentication, containers, or external network access require explicit security review against [docs/security.md](docs/security.md) and architectural review against [docs/architecture.md](docs/architecture.md).

### Tests and contracts

- Add focused tests for changed behavior and regressions.
- Preserve conservative abstention and last-known-good activation behavior.
- Keep CLI, FastAPI, React, and generated JSON Schemas aligned where they share a public contract.
- Regenerate schemas and lockfiles with project tooling; never hand-edit them.
- Keep examples deterministic and free of credentials or private data.
- Do not reduce coverage, type safety, validation, authentication, sandboxing, or resource limits without a documented and approved reason.

### Dependencies and licenses

Use exact direct dependency versions and committed lockfiles. An AI coding agent must verify the intended upstream package before adding it, prefer existing dependencies or the standard library, and identify license or supply-chain implications in the pull request. Do not copy incompatible or unattributed code or documentation.

## Reporting security issues

Do not open a public issue or pull request containing an exploitable vulnerability, credentials, source documents, generated proprietary rules, or database contents. Report security issues privately to the repository owner. Any resulting repository fix must still be authored by an AI coding agent and merged through the normal private-to-public remediation and pull-request process.