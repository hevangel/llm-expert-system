"""Deterministic capability routing and routing-proposal policy validation."""

from __future__ import annotations

from collections import defaultdict, deque

from .models import (
    Capability,
    Engine,
    EngineHealth,
    QueryRequest,
    RoutingPlan,
    RoutingProposal,
    RoutingStep,
)

_CAPABILITY_ENGINE = {
    Capability.RELATIONAL: Engine.PROLOG,
    Capability.FORWARD_CHAINING: Engine.CLIPS,
    Capability.CONSTRAINT: Engine.Z3,
    Capability.OPTIMIZATION: Engine.Z3,
    Capability.PLANNING: Engine.CLINGO,
    Capability.NON_MONOTONIC: Engine.CLINGO,
}


class RoutingPolicy:
    def route(
        self,
        request: QueryRequest,
        health: tuple[EngineHealth, ...],
        proposal: RoutingProposal | None = None,
    ) -> RoutingPlan:
        available = {item.engine for item in health if item.available}
        if proposal is None:
            capabilities = request.capabilities or (Capability.RELATIONAL,)
            steps = tuple(
                RoutingStep(
                    id=f"step_{index}",
                    engine=_CAPABILITY_ENGINE[capability],
                    capability=capability,
                    depends_on=(f"step_{index - 1}",) if index else (),
                )
                for index, capability in enumerate(dict.fromkeys(capabilities))
            )
            proposal = RoutingProposal(steps=steps, rationale="deterministic capability policy")
        self._validate(proposal, available)
        return RoutingPlan(
            steps=proposal.steps,
            rationale=proposal.rationale,
            fallback="abstain",
            policy_validated=True,
        )

    def _validate(self, proposal: RoutingProposal, available: set[Engine]) -> None:
        ids = {step.id for step in proposal.steps}
        if len(ids) != len(proposal.steps):
            raise ValueError("routing step IDs must be unique")
        for step in proposal.steps:
            if step.engine != _CAPABILITY_ENGINE[step.capability]:
                raise ValueError(f"{step.engine} is not approved for {step.capability}")
            if step.engine not in available:
                raise ValueError(f"engine unavailable: {step.engine}")
            if not set(step.depends_on) <= ids:
                raise ValueError(f"unknown dependency in step {step.id}")
        indegree = {step.id: len(step.depends_on) for step in proposal.steps}
        children: dict[str, list[str]] = defaultdict(list)
        for step in proposal.steps:
            for dependency in step.depends_on:
                children[dependency].append(step.id)
        queue = deque(step for step, degree in indegree.items() if degree == 0)
        visited = 0
        while queue:
            current = queue.popleft()
            visited += 1
            for child in children[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if visited != len(proposal.steps):
            raise ValueError("routing plan contains a cycle")
