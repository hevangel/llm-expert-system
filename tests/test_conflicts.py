from llm_expert_system.conflicts import ConflictAnalyzer
from llm_expert_system.models import Atom, EvidenceRef, Fact, KnowledgeBase, KnowledgeItemState


def fact(identifier: str, negated: bool, predicate: str = "operational") -> Fact:
    evidence = EvidenceRef.from_text("doc", f"line:{identifier}", identifier)
    return Fact(id=identifier, state=KnowledgeItemState.ACCEPTED, evidence=(evidence,), atom=Atom(predicate=predicate, arguments=("pump",), negated=negated))


def test_detects_opposite_facts_and_scopes_affected_predicate() -> None:
    knowledge = KnowledgeBase(facts=(fact("pump_works", False), fact("pump_broken", True), fact("safe_fact", False, "located")))
    analyzed = ConflictAnalyzer().with_conflicts(knowledge)
    assert len(analyzed.conflicts) == 1
    assert analyzed.conflicts[0].affected_predicates == ("operational",)
    assert analyzed.facts[2].state == KnowledgeItemState.ACCEPTED
