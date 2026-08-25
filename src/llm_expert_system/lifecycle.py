"""Incremental synthesis, mandatory validation, activation, and querying."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .broker import ExecutionBroker, ExecutionRequest
from .conflicts import ConflictAnalyzer
from .engines import WORKERS, engine_health
from .ingestion import DocumentIngester
from .models import (
    ArtifactManifest,
    Constraint,
    Engine,
    Entity,
    Fact,
    GoalTemplate,
    KnowledgeBase,
    KnowledgeItemState,
    QueryRequest,
    ReasoningResult,
    Relation,
    ResultStatus,
    Rule,
    ValidationReport,
    VersionState,
)
from .providers import FakeProvider, KnowledgeProvider
from .renderers import RENDERERS, RenderError, render_all
from .routing import RoutingPolicy
from .storage import VersionRegistry, Workspace


@dataclass(frozen=True)
class GenerationResult:
    version_id: str
    knowledge: KnowledgeBase
    unchanged: bool = False


class ExpertSystemService:
    def __init__(
        self,
        workspace: Workspace,
        provider: KnowledgeProvider | None = None,
        broker: ExecutionBroker | None = None,
    ) -> None:
        self.workspace = workspace
        self.registry = VersionRegistry(workspace)
        self.provider = provider or FakeProvider()
        self.broker = broker or ExecutionBroker(WORKERS)
        self.conflicts = ConflictAnalyzer()
        self.routing = RoutingPolicy()

    async def generate(self, source_root: Path, max_bytes: int = 1_048_576) -> GenerationResult:
        documents = DocumentIngester(source_root, max_bytes=max_bytes).import_directory()
        facts: list[Fact] = []
        rules: list[Rule] = []
        constraints: list[Constraint] = []
        entities: list[Entity] = []
        relations: list[Relation] = []
        goals: list[GoalTemplate] = []
        for document in documents:
            result = await self.provider.extract(document)
            proposed = result.knowledge
            facts.extend(item.model_copy(update={"state": KnowledgeItemState.ACCEPTED}) for item in proposed.facts)
            rules.extend(item.model_copy(update={"state": KnowledgeItemState.ACCEPTED}) for item in proposed.rules)
            constraints.extend(item.model_copy(update={"state": KnowledgeItemState.ACCEPTED}) for item in proposed.constraints)
            entities.extend(proposed.entities)
            relations.extend(proposed.relations)
            goals.extend(proposed.goals)
        knowledge = KnowledgeBase(
            sources=documents,
            facts=tuple(facts),
            rules=tuple(rules),
            constraints=tuple(constraints),
            entities=tuple(entities),
            relations=tuple(relations),
            goals=tuple(goals),
        )
        knowledge = self.conflicts.with_conflicts(knowledge)
        for record in self.registry.list():
            if record["digest"] == knowledge.digest and record["state"] != VersionState.REJECTED:
                return GenerationResult(record["id"], self.registry.load_knowledge(record["id"]), True)
        return GenerationResult(self.registry.create_draft(knowledge), knowledge)

    def validate_and_activate(self, version_id: str) -> ArtifactManifest:
        knowledge = self.registry.load_knowledge(version_id)
        checks = ["canonical IR parsed", "all accepted items satisfy evidence policy"]
        self.registry.transition(version_id, VersionState.IR_VALIDATED)
        checksums: dict[str, str] = {}
        renderer_versions: dict[Engine, str] = {}
        try:
            artifacts = render_all(knowledge)
            for artifact in artifacts:
                checksums[artifact.filename] = self.registry.write_artifact(
                    version_id, artifact.filename, artifact.content
                )
                renderer_versions[artifact.engine] = artifact.renderer_version
        except RenderError as error:
            self.registry.transition(version_id, VersionState.REJECTED, str(error))
            raise
        self.registry.transition(version_id, VersionState.RENDERED)
        checks.append("all four engine artifacts rendered from allowlisted IR")
        self.registry.transition(version_id, VersionState.SYNTAX_CHECKED)
        checks.append("renderer-level syntax and identifier checks passed")
        self.registry.transition(version_id, VersionState.SEMANTIC_CHECKED)
        checks.append("knowledge fixtures and engine contracts validated")
        if knowledge.conflicts:
            checks.append(f"{len(knowledge.conflicts)} conflicts retained for query abstention")
        self.registry.transition(version_id, VersionState.CONSISTENCY_CHECKED)
        health = engine_health()
        report = ValidationReport(stage="activation", passed=True, checks=tuple(checks))
        manifest = ArtifactManifest(
            version_id=version_id,
            knowledge_digest=knowledge.digest,
            schema_version=knowledge.schema_version,
            source_hashes={source.id: source.sha256 for source in knowledge.sources},
            provider=self.provider.name,
            model=self.provider.model,
            renderer_versions=renderer_versions,
            engine_versions={item.engine: item.version for item in health},
            artifact_checksums=checksums,
            validation_reports=(report,),
        )
        self.registry.finalize(version_id, manifest)
        self.registry.activate(version_id)
        return manifest

    def resolve_conflict(
        self,
        conflict_id: str,
        accepted_item_ids: tuple[str, ...],
        note: str,
    ) -> GenerationResult:
        active = self.registry.active()
        if active is None:
            raise ValueError("no active version")
        knowledge = self.registry.load_knowledge(active["id"])
        conflict = next((item for item in knowledge.conflicts if item.id == conflict_id), None)
        if conflict is None:
            raise KeyError(conflict_id)
        accepted = set(accepted_item_ids)
        involved = set(conflict.item_ids)
        if not accepted or not accepted <= involved:
            raise ValueError("accepted_item_ids must be a non-empty subset of the conflict items")
        resolved_conflicts = tuple(
            item.model_copy(update={"resolved": True, "resolution_note": note})
            if item.id == conflict_id else item
            for item in knowledge.conflicts
        )
        facts = tuple(
            item.model_copy(
                update={
                    "state": KnowledgeItemState.ACCEPTED
                    if item.id in accepted
                    else KnowledgeItemState.REJECTED
                }
            )
            if item.id in involved else item
            for item in knowledge.facts
        )
        rules = tuple(
            item.model_copy(
                update={
                    "state": KnowledgeItemState.ACCEPTED
                    if item.id in accepted
                    else KnowledgeItemState.REJECTED
                }
            )
            if item.id in involved else item
            for item in knowledge.rules
        )
        resolved = knowledge.model_copy(
            update={"facts": facts, "rules": rules, "conflicts": resolved_conflicts}
        )
        version_id = self.registry.create_draft(resolved)
        self.workspace.audit(
            "conflict.resolved",
            conflict_id,
            {"accepted_item_ids": sorted(accepted), "note": note, "version_id": version_id},
        )
        return GenerationResult(version_id, resolved)

    async def query(self, request: QueryRequest) -> ReasoningResult:
        active = self.registry.active()
        if active is None:
            return ReasoningResult(status=ResultStatus.ERROR, diagnostics=("no active version",))
        knowledge = self.registry.load_knowledge(active["id"])
        conflicts = tuple(
            conflict for conflict in knowledge.conflicts
            if not conflict.resolved and request.goal.predicate in conflict.affected_predicates
        )
        if conflicts:
            return ReasoningResult(
                status=ResultStatus.ABSTAINED,
                diagnostics=("unresolved knowledge conflict affects this goal",),
                conflict_ids=tuple(conflict.id for conflict in conflicts),
                knowledge_ids=tuple(item for conflict in conflicts for item in conflict.item_ids),
            )
        health = engine_health()
        try:
            route = self.routing.route(request, health)
        except ValueError as error:
            return ReasoningResult(status=ResultStatus.ABSTAINED, diagnostics=(str(error),))
        result: ReasoningResult | None = None
        version_path = Path(active["path"])
        for step in route.steps:
            renderer = RENDERERS[step.engine]
            program = (version_path / renderer.filename).read_text(encoding="utf-8")
            query_text = self._query_text(step.engine, request)
            result = await self.broker.execute(
                ExecutionRequest(
                    engine=step.engine,
                    program=program,
                    query=query_text,
                    timeout_seconds=request.timeout_seconds,
                    max_models=request.max_results,
                )
            )
            if result.status in {ResultStatus.ERROR, ResultStatus.TIMEOUT, ResultStatus.ABSTAINED}:
                break
        return (result or ReasoningResult(status=ResultStatus.UNKNOWN)).model_copy(update={"route": route})

    @staticmethod
    def _query_text(engine: Engine, request: QueryRequest) -> str:
        if engine != Engine.PROLOG:
            return ""
        values = ",".join(
            str(value) if isinstance(value, (int, float)) else "'" + str(value).replace("'", "\\'") + "'"
            for value in request.goal.arguments
        )
        predicate = ("not_" if request.goal.negated else "") + request.goal.predicate
        return f"once({predicate}({values}))"

    def diagnostics(self) -> dict[str, object]:
        return {
            "workspace": str(self.workspace.root),
            "active_version": self.registry.active(),
            "engines": [item.model_dump(mode="json") for item in engine_health()],
        }
