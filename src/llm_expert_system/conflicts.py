"""Conservative deterministic conflict detection."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from .models import (
    ConflictRecord,
    ExprOp,
    Fact,
    KnowledgeBase,
    KnowledgeItemState,
    Rule,
)


class ConflictAnalyzer:
    """Find only explicit contradictions; uncertainty is never confidence-merged."""

    def analyze(self, knowledge: KnowledgeBase) -> tuple[ConflictRecord, ...]:
        conflicts: list[ConflictRecord] = []
        grouped: dict[tuple[str, tuple[object, ...]], dict[bool, list[Fact]]] = defaultdict(
            lambda: {False: [], True: []}
        )
        for fact in knowledge.facts:
            if fact.state not in {KnowledgeItemState.ACCEPTED, KnowledgeItemState.PROPOSED}:
                continue
            grouped[(fact.atom.predicate, fact.atom.arguments)][fact.atom.negated].append(fact)
        for (predicate, _), fact_polarities in grouped.items():
            if fact_polarities[False] and fact_polarities[True]:
                fact_items = tuple(fact_polarities[False] + fact_polarities[True])
                conflicts.append(
                    self._record(
                        "opposite_facts",
                        tuple(item.id for item in fact_items),
                        (predicate,),
                        tuple(evidence for item in fact_items for evidence in item.evidence),
                    )
                )

        conclusions: dict[tuple[str, tuple[object, ...]], dict[bool, list[Rule]]] = defaultdict(
            lambda: {False: [], True: []}
        )
        for rule in knowledge.rules:
            conclusions[(rule.then.predicate, rule.then.arguments)][rule.then.negated].append(rule)
        for (predicate, _), rule_polarities in conclusions.items():
            if rule_polarities[False] and rule_polarities[True]:
                rule_items = tuple(rule_polarities[False] + rule_polarities[True])
                conflicts.append(
                    self._record(
                        "incompatible_conclusions",
                        tuple(item.id for item in rule_items),
                        (predicate,),
                        tuple(evidence for item in rule_items for evidence in item.evidence),
                    )
                )

        relation_shapes: dict[str, set[int]] = defaultdict(set)
        for relation in knowledge.relations:
            relation_shapes[relation.id].add(relation.arity)
        for relation_id, arities in relation_shapes.items():
            if len(arities) > 1:
                conflicts.append(
                    self._record(
                        "ambiguous_definition",
                        tuple(f"{relation_id}/{arity}" for arity in sorted(arities)),
                        (relation_id,),
                        (),
                    )
                )

        for constraint in knowledge.constraints:
            expression = constraint.expression
            if expression.op == ExprOp.LITERAL and expression.value is False:
                conflicts.append(
                    self._record(
                        "unsatisfiable",
                        (constraint.id, f"{constraint.id}_false"),
                        tuple(goal.predicate for goal in knowledge.goals) or ("constraint",),
                        constraint.evidence,
                    )
                )
        return tuple(conflicts)

    @staticmethod
    def _record(
        category: str,
        item_ids: tuple[str, ...],
        predicates: tuple[str, ...],
        evidence: tuple[object, ...],
    ) -> ConflictRecord:
        seed = f"{category}:{'|'.join(item_ids)}"
        return ConflictRecord(
            id=f"conflict-{hashlib.sha256(seed.encode()).hexdigest()[:16]}",
            category=category,  # type: ignore[arg-type]
            item_ids=item_ids,
            affected_predicates=predicates,
            evidence=evidence,  # type: ignore[arg-type]
        )

    def with_conflicts(self, knowledge: KnowledgeBase) -> KnowledgeBase:
        conflicts = self.analyze(knowledge)
        affected_ids = {item_id for conflict in conflicts for item_id in conflict.item_ids}
        facts = tuple(
            fact.model_copy(update={"state": KnowledgeItemState.CONFLICTED})
            if fact.id in affected_ids else fact
            for fact in knowledge.facts
        )
        rules = tuple(
            rule.model_copy(update={"state": KnowledgeItemState.CONFLICTED})
            if rule.id in affected_ids else rule
            for rule in knowledge.rules
        )
        return knowledge.model_copy(update={"facts": facts, "rules": rules, "conflicts": conflicts})
