"""Reproducible evaluation harness for bundled scenarios."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .lifecycle import ExpertSystemService
from .engines import engine_health
from .storage import Workspace


@dataclass(frozen=True)
class EvaluationReport:
    version_id: str
    source_count: int
    fact_count: int
    provenance_coverage: float
    conflict_count: int
    activation_seconds: float
    engine_health: dict[str, bool]
    passed: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


async def evaluate(source_root: Path, workspace: Path) -> EvaluationReport:
    service = ExpertSystemService(Workspace(workspace))
    started = time.monotonic()
    generated = await service.generate(source_root)
    if not generated.unchanged:
        service.validate_and_activate(generated.version_id)
    elapsed = time.monotonic() - started
    knowledge = service.registry.load_knowledge(generated.version_id)
    evidenced = sum(bool(fact.evidence) for fact in knowledge.facts)
    coverage = evidenced / len(knowledge.facts) if knowledge.facts else 1.0
    health_records = engine_health()
    health = {item.engine.value: item.available for item in health_records}
    return EvaluationReport(
        version_id=generated.version_id,
        source_count=len(knowledge.sources),
        fact_count=len(knowledge.facts),
        provenance_coverage=coverage,
        conflict_count=len(knowledge.conflicts),
        activation_seconds=elapsed,
        engine_health=health,
        passed=coverage == 1.0,
    )


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--workspace", type=Path, default=Path(".evaluation-workspace"))
    arguments = parser.parse_args()
    print(asyncio.run(evaluate(arguments.source, arguments.workspace)).to_json())


if __name__ == "__main__":
    main()
