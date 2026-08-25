from llm_expert_system.models import (
    Atom, Constraint, EvidenceRef, ExprOp, Expression, Fact, KnowledgeBase, KnowledgeItemState, Rule,
)
from llm_expert_system.renderers import render_all


def knowledge() -> KnowledgeBase:
    evidence = (EvidenceRef.from_text("doc", "lines:1-1", "source"),)
    parent = Fact(id="parent_fact", state=KnowledgeItemState.ACCEPTED, evidence=evidence, atom=Atom(predicate="parent", arguments=("alice", "bob")))
    rule = Rule(id="ancestor_rule", state=KnowledgeItemState.ACCEPTED, evidence=evidence, when=(Atom(predicate="parent", arguments=("?x", "?y")),), then=Atom(predicate="ancestor", arguments=("?x", "?y")))
    constraint = Constraint(id="capacity_rule", state=KnowledgeItemState.ACCEPTED, evidence=evidence, expression=Expression(op=ExprOp.LE, args=(Expression(op=ExprOp.VARIABLE, name="load"), Expression(op=ExprOp.LITERAL, value=10))))
    return KnowledgeBase(facts=(parent,), rules=(rule,), constraints=(constraint,))


def test_all_renderers_produce_safe_deterministic_artifacts() -> None:
    first = render_all(knowledge())
    second = render_all(knowledge())
    assert len(first) == 4
    assert [(item.filename, item.content) for item in first] == [(item.filename, item.content) for item in second]
    contents = {item.filename: item.content for item in first}
    assert "parent('alice', 'bob')." in contents["knowledge.pl"]
    assert "(defrule rule_ancestor_rule" in contents["knowledge.clp"]
    assert "(assert (<= load 10))" in contents["knowledge.smt2"]
    assert 'parent("alice", "bob").' in contents["knowledge.lp"]
