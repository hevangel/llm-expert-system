import pytest
from pydantic import ValidationError

from llm_expert_system.models import (
    Atom, EvidenceRef, ExprOp, Expression, Fact, KnowledgeBase, KnowledgeItemState,
)


def evidence() -> EvidenceRef:
    return EvidenceRef.from_text("doc-1", "lines:1-1", "Alice is parent of Bob.")


def test_accepted_knowledge_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="requires evidence"):
        Fact(id="missing_evidence", state=KnowledgeItemState.ACCEPTED, atom=Atom(predicate="parent"))


def test_canonical_digest_is_stable() -> None:
    fact = Fact(id="parent_fact", state=KnowledgeItemState.ACCEPTED, atom=Atom(predicate="parent", arguments=("alice", "bob")), evidence=(evidence(),))
    first = KnowledgeBase(facts=(fact,))
    second = KnowledgeBase.model_validate_json(first.canonical_json())
    assert first.digest == second.digest


def test_expression_rejects_invalid_shape_and_depth() -> None:
    with pytest.raises(ValidationError):
        Expression(op=ExprOp.EQ, args=())
    expression = Expression(op=ExprOp.LITERAL, value=True)
    for _ in range(23):
        expression = Expression(op=ExprOp.NOT, args=(expression,))
    with pytest.raises(ValidationError, match="nesting"):
        Expression(op=ExprOp.NOT, args=(expression,))
