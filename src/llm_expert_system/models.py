"""Canonical, engine-neutral knowledge representation and runtime contracts."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
Scalar = str | int | float | bool


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Engine(StrEnum):
    PROLOG = "prolog"
    CLIPS = "clips"
    Z3 = "z3"
    CLINGO = "clingo"


class Capability(StrEnum):
    RELATIONAL = "relational"
    FORWARD_CHAINING = "forward_chaining"
    CONSTRAINT = "constraint"
    OPTIMIZATION = "optimization"
    PLANNING = "planning"
    NON_MONOTONIC = "non_monotonic"


class KnowledgeItemState(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    CONFLICTED = "conflicted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class VersionState(StrEnum):
    DRAFT = "draft"
    IR_VALIDATED = "ir_validated"
    RENDERED = "rendered"
    SYNTAX_CHECKED = "syntax_checked"
    SEMANTIC_CHECKED = "semantic_checked"
    CONSISTENCY_CHECKED = "consistency_checked"
    STAGED = "staged"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class ResultStatus(StrEnum):
    ANSWERED = "answered"
    UNKNOWN = "unknown"
    UNSAT = "unsat"
    ABSTAINED = "abstained"
    ERROR = "error"
    TIMEOUT = "timeout"


class SourceSection(StrictModel):
    id: str
    locator: str
    text: str = Field(max_length=1_048_576)


class SourceDocument(StrictModel):
    id: str
    relative_path: str
    media_type: Literal["text/markdown", "text/plain", "application/json", "application/yaml"]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    imported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parser_version: str = "1"
    sections: tuple[SourceSection, ...]


class EvidenceRef(StrictModel):
    document_id: str
    locator: str
    excerpt_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    excerpt: str | None = Field(default=None, max_length=500)

    @classmethod
    def from_text(cls, document_id: str, locator: str, text: str) -> EvidenceRef:
        return cls(
            document_id=document_id,
            locator=locator,
            excerpt_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            excerpt=text[:500],
        )


class Confidence(StrictModel):
    score: float = Field(ge=0, le=1)
    rationale: str | None = Field(default=None, max_length=500)


class EngineHint(StrictModel):
    engine: Engine
    capability: Capability
    rationale: str = Field(max_length=500)


class Entity(StrictModel):
    id: Identifier
    label: str = Field(min_length=1, max_length=200)
    type: Identifier = "entity"
    evidence: tuple[EvidenceRef, ...] = ()


class Relation(StrictModel):
    id: Identifier
    arity: int = Field(ge=1, le=16)
    argument_types: tuple[Identifier, ...] = ()
    evidence: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def validate_argument_types(self) -> Relation:
        if self.argument_types and len(self.argument_types) != self.arity:
            raise ValueError("argument_types must be empty or match arity")
        return self


class Atom(StrictModel):
    predicate: Identifier
    arguments: tuple[Scalar, ...] = Field(default=(), max_length=16)
    negated: bool = False

    @model_validator(mode="after")
    def validate_arguments(self) -> Atom:
        for value in self.arguments:
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("atom arguments must contain finite numbers")
            if isinstance(value, str):
                if len(value) > 500:
                    raise ValueError("atom string arguments are limited to 500 characters")
                if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
                    raise ValueError("atom string arguments contain unsupported control characters")
        return self


class ExprOp(StrEnum):
    LITERAL = "literal"
    VARIABLE = "variable"
    AND = "and"
    OR = "or"
    NOT = "not"
    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LE = "le"
    GT = "gt"
    GE = "ge"
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    IMPLIES = "implies"


class Expression(StrictModel):
    op: ExprOp
    value: Scalar | None = None
    name: Identifier | None = None
    args: tuple[Expression, ...] = ()

    @model_validator(mode="after")
    def validate_shape(self) -> Expression:
        counts: dict[ExprOp, tuple[int, int]] = {
            ExprOp.LITERAL: (0, 0), ExprOp.VARIABLE: (0, 0), ExprOp.NOT: (1, 1),
            ExprOp.AND: (2, 32), ExprOp.OR: (2, 32), ExprOp.IMPLIES: (2, 2),
            ExprOp.EQ: (2, 2), ExprOp.NE: (2, 2), ExprOp.LT: (2, 2),
            ExprOp.LE: (2, 2), ExprOp.GT: (2, 2), ExprOp.GE: (2, 2),
            ExprOp.ADD: (2, 32), ExprOp.SUB: (2, 2), ExprOp.MUL: (2, 32), ExprOp.DIV: (2, 2),
        }
        low, high = counts[self.op]
        if not low <= len(self.args) <= high:
            raise ValueError(f"{self.op} requires {low}..{high} arguments")
        if self.op == ExprOp.LITERAL and self.value is None:
            raise ValueError("literal expression requires value")
        if self.op == ExprOp.VARIABLE and self.name is None:
            raise ValueError("variable expression requires name")
        if self.depth > 24:
            raise ValueError("expression nesting exceeds 24")
        return self

    @property
    def depth(self) -> int:
        return 1 + max((child.depth for child in self.args), default=0)


class KnowledgeItem(StrictModel):
    id: Identifier
    state: KnowledgeItemState = KnowledgeItemState.PROPOSED
    evidence: tuple[EvidenceRef, ...] = ()
    confidence: Confidence | None = None
    engine_hints: tuple[EngineHint, ...] = ()
    system_axiom: bool = False

    @model_validator(mode="after")
    def require_accepted_evidence(self) -> KnowledgeItem:
        if self.state == KnowledgeItemState.ACCEPTED and not self.evidence and not self.system_axiom:
            raise ValueError("accepted knowledge requires evidence or system_axiom=true")
        return self


class Fact(KnowledgeItem):
    atom: Atom


class Rule(KnowledgeItem):
    when: tuple[Atom, ...] = Field(min_length=1, max_length=64)
    then: Atom
    priority: int = Field(default=0, ge=-1000, le=1000)


class Constraint(KnowledgeItem):
    expression: Expression


class GoalTemplate(KnowledgeItem):
    predicate: Identifier
    parameters: tuple[Identifier, ...] = ()
    capabilities: tuple[Capability, ...] = ()


class ConflictRecord(StrictModel):
    id: str
    category: Literal[
        "opposite_facts", "incompatible_conclusions", "unsatisfiable",
        "ambiguous_definition", "cross_engine_disagreement"
    ]
    item_ids: tuple[str, ...] = Field(min_length=2)
    affected_predicates: tuple[Identifier, ...]
    evidence: tuple[EvidenceRef, ...] = ()
    resolved: bool = False
    resolution_note: str | None = Field(default=None, max_length=1000)


class KnowledgeBase(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    sources: tuple[SourceDocument, ...] = Field(default=(), max_length=10_000)
    entities: tuple[Entity, ...] = Field(default=(), max_length=10_000)
    relations: tuple[Relation, ...] = Field(default=(), max_length=10_000)
    facts: tuple[Fact, ...] = Field(default=(), max_length=100_000)
    rules: tuple[Rule, ...] = Field(default=(), max_length=100_000)
    constraints: tuple[Constraint, ...] = Field(default=(), max_length=100_000)
    goals: tuple[GoalTemplate, ...] = Field(default=(), max_length=10_000)
    conflicts: tuple[ConflictRecord, ...] = Field(default=(), max_length=100_000)

    @model_validator(mode="after")
    def validate_predicate_signatures_and_rules(self) -> KnowledgeBase:
        signatures = {relation.id: relation.arity for relation in self.relations}

        def register(atom: Atom) -> None:
            arity = len(atom.arguments)
            previous = signatures.setdefault(atom.predicate, arity)
            if previous != arity:
                raise ValueError(f"predicate {atom.predicate} has inconsistent arity")

        for fact in self.facts:
            register(fact.atom)
        for rule in self.rules:
            for atom in (*rule.when, rule.then):
                register(atom)
            body_variables = {
                value
                for atom in rule.when
                for value in atom.arguments
                if isinstance(value, str) and value.startswith("?")
            }
            head_variables = {
                value
                for value in rule.then.arguments
                if isinstance(value, str) and value.startswith("?")
            }
            if not head_variables <= body_variables:
                raise ValueError(f"rule {rule.id} has variables in its conclusion not bound in its body")
        return self

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    @property
    def digest(self) -> str:
        payload = self.model_dump(mode="json")
        for source in payload["sources"]:
            source.pop("imported_at", None)
        semantic_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(semantic_json.encode()).hexdigest()


class QueryRequest(StrictModel):
    goal: Atom
    capabilities: tuple[Capability, ...] = Field(default=(), max_length=8)
    require_proof: bool = False
    require_models: bool = False
    optimize: bool = False
    max_results: int = Field(default=10, ge=1, le=1000)
    timeout_seconds: float = Field(default=10, gt=0, le=300)

    @model_validator(mode="after")
    def require_ground_goal(self) -> QueryRequest:
        if any(isinstance(value, str) and value.startswith("?") for value in self.goal.arguments):
            raise ValueError("query goals must be ground; variable strings are not accepted")
        return self


class EngineHealth(StrictModel):
    engine: Engine
    available: bool
    version: str | None = None
    detail: str | None = None


class RoutingStep(StrictModel):
    id: Identifier
    engine: Engine
    depends_on: tuple[Identifier, ...] = ()
    capability: Capability


class RoutingProposal(StrictModel):
    steps: tuple[RoutingStep, ...] = Field(min_length=1, max_length=8)
    rationale: str = Field(max_length=1000)


class RoutingPlan(RoutingProposal):
    fallback: Literal["abstain", "unknown"] = "abstain"
    policy_validated: bool = True


class ReasoningResult(StrictModel):
    status: ResultStatus
    engine: Engine | None = None
    bindings: tuple[dict[str, Any], ...] = ()
    models: tuple[tuple[str, ...], ...] = ()
    objective: Scalar | None = None
    diagnostics: tuple[str, ...] = ()
    proof: tuple[str, ...] = ()
    knowledge_ids: tuple[str, ...] = ()
    conflict_ids: tuple[str, ...] = ()
    route: RoutingPlan | None = None


class ValidationReport(StrictModel):
    stage: str
    passed: bool
    checks: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ArtifactManifest(StrictModel):
    version_id: str
    knowledge_digest: str
    schema_version: str
    source_hashes: dict[str, str]
    provider: str
    model: str
    template_version: str = "1"
    renderer_versions: dict[Engine, str]
    engine_versions: dict[Engine, str | None] = {}
    artifact_checksums: dict[str, str] = {}
    validation_reports: tuple[ValidationReport, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
