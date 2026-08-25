"""Deterministic renderers from the allowlisted IR to engine source files."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from .models import Atom, Engine, ExprOp, Expression, KnowledgeBase, KnowledgeItemState, Scalar

_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class RenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderedArtifact:
    engine: Engine
    filename: str
    content: str
    renderer_version: str = "1"


class Renderer(Protocol):
    engine: Engine
    filename: str
    def render(self, knowledge: KnowledgeBase) -> RenderedArtifact: ...


def _identifier(value: str) -> str:
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise RenderError(f"unsafe identifier: {value!r}")
    return value


def _prolog_value(value: Scalar) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value.startswith("?") and _SAFE_IDENTIFIER.fullmatch(value[1:].lower()):
        return value[1:].capitalize()
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _clips_value(value: Scalar) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if value.startswith("?") and _SAFE_IDENTIFIER.fullmatch(value[1:].lower()):
        return "?" + value[1:].lower()
    return json.dumps(value)


def _atom(atom: Atom, formatter: object, negative_prefix: str = "not_") -> str:
    predicate = (negative_prefix if atom.negated else "") + _identifier(atom.predicate)
    values = ", ".join(formatter(value) for value in atom.arguments)  # type: ignore[operator]
    return f"{predicate}({values})"


class PrologRenderer:
    engine = Engine.PROLOG
    filename = "knowledge.pl"

    def render(self, knowledge: KnowledgeBase) -> RenderedArtifact:
        lines = [":- set_prolog_flag(unknown, fail).", "% Generated; do not edit."]
        for fact in knowledge.facts:
            if fact.state == KnowledgeItemState.ACCEPTED:
                lines.append(_atom(fact.atom, _prolog_value) + ".")
        for rule in knowledge.rules:
            if rule.state == KnowledgeItemState.ACCEPTED:
                head = _atom(rule.then, _prolog_value)
                body = ", ".join(_atom(atom, _prolog_value) for atom in rule.when)
                lines.append(f"{head} :- {body}.")
        return RenderedArtifact(self.engine, self.filename, "\n".join(lines) + "\n")


def _clingo_value(value: Scalar) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value.startswith("?") and _SAFE_IDENTIFIER.fullmatch(value[1:].lower()):
        return value[1:].capitalize()
    return json.dumps(value)


def _clingo_atom(atom: Atom) -> str:
    prefix = "-" if atom.negated else ""
    values = ", ".join(_clingo_value(value) for value in atom.arguments)
    return f"{prefix}{_identifier(atom.predicate)}({values})"


class ClingoRenderer:
    engine = Engine.CLINGO
    filename = "knowledge.lp"

    def render(self, knowledge: KnowledgeBase) -> RenderedArtifact:
        lines = ["% Generated; do not edit."]
        for fact in knowledge.facts:
            if fact.state == KnowledgeItemState.ACCEPTED:
                lines.append(_clingo_atom(fact.atom) + ".")
        for rule in knowledge.rules:
            if rule.state == KnowledgeItemState.ACCEPTED:
                head = _clingo_atom(rule.then)
                body = ", ".join(_clingo_atom(atom) for atom in rule.when)
                lines.append(f"{head} :- {body}.")
        return RenderedArtifact(self.engine, self.filename, "\n".join(lines) + "\n")


class ClipsRenderer:
    engine = Engine.CLIPS
    filename = "knowledge.clp"

    def render(self, knowledge: KnowledgeBase) -> RenderedArtifact:
        lines = ["; Generated; do not edit."]
        for fact in knowledge.facts:
            if fact.state == KnowledgeItemState.ACCEPTED:
                predicate = ("not_" if fact.atom.negated else "") + _identifier(fact.atom.predicate)
                values = " ".join(_clips_value(value) for value in fact.atom.arguments)
                lines.append(f"(deffacts fact_{fact.id} ({predicate} {values}))")
        for rule in knowledge.rules:
            if rule.state == KnowledgeItemState.ACCEPTED:
                conditions = " ".join(self._atom(atom) for atom in rule.when)
                conclusion = self._atom(rule.then)
                lines.append(f"(defrule rule_{rule.id} (declare (salience {rule.priority})) {conditions} => (assert {conclusion}))")
        return RenderedArtifact(self.engine, self.filename, "\n".join(lines) + "\n")

    @staticmethod
    def _atom(atom: Atom) -> str:
        predicate = ("not_" if atom.negated else "") + _identifier(atom.predicate)
        values = " ".join(_clips_value(value) for value in atom.arguments)
        return f"({predicate} {values})"


class Z3Renderer:
    engine = Engine.Z3
    filename = "knowledge.smt2"

    def render(self, knowledge: KnowledgeBase) -> RenderedArtifact:
        variables: set[str] = set()
        for constraint in knowledge.constraints:
            self._collect_variables(constraint.expression, variables)
        lines = ["; Generated; do not edit.", "(set-logic ALL)"]
        for variable in sorted(variables):
            lines.append(f"(declare-const {_identifier(variable)} Int)")
        for constraint in knowledge.constraints:
            if constraint.state == KnowledgeItemState.ACCEPTED:
                lines.append(f"; {constraint.id}")
                lines.append(f"(assert {self._expression(constraint.expression)})")
        lines.append("(check-sat)")
        lines.append("(get-model)")
        return RenderedArtifact(self.engine, self.filename, "\n".join(lines) + "\n")

    def _expression(self, expression: Expression) -> str:
        if expression.op == ExprOp.LITERAL:
            if isinstance(expression.value, bool):
                return "true" if expression.value else "false"
            if isinstance(expression.value, (int, float)):
                return str(expression.value)
            raise RenderError("Z3 string literals are not enabled in IR version 1")
        if expression.op == ExprOp.VARIABLE:
            return _identifier(expression.name or "")
        operators = {
            ExprOp.AND: "and", ExprOp.OR: "or", ExprOp.NOT: "not", ExprOp.EQ: "=",
            ExprOp.NE: "distinct", ExprOp.LT: "<", ExprOp.LE: "<=", ExprOp.GT: ">",
            ExprOp.GE: ">=", ExprOp.ADD: "+", ExprOp.SUB: "-", ExprOp.MUL: "*",
            ExprOp.DIV: "div", ExprOp.IMPLIES: "=>",
        }
        return f"({operators[expression.op]} {' '.join(self._expression(arg) for arg in expression.args)})"

    def _collect_variables(self, expression: Expression, variables: set[str]) -> None:
        if expression.op == ExprOp.VARIABLE and expression.name:
            variables.add(expression.name)
        for child in expression.args:
            self._collect_variables(child, variables)


RENDERERS: dict[Engine, Renderer] = {
    Engine.PROLOG: PrologRenderer(),
    Engine.CLIPS: ClipsRenderer(),
    Engine.Z3: Z3Renderer(),
    Engine.CLINGO: ClingoRenderer(),
}


def render_all(knowledge: KnowledgeBase) -> tuple[RenderedArtifact, ...]:
    return tuple(renderer.render(knowledge) for renderer in RENDERERS.values())
