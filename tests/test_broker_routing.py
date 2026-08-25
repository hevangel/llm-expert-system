import pytest

from llm_expert_system.broker import ExecutionBroker, ExecutionRequest, FakeWorker
from llm_expert_system.models import Capability, Engine, EngineHealth, QueryRequest, Atom, ResultStatus, RoutingProposal, RoutingStep
from llm_expert_system.routing import RoutingPolicy


@pytest.mark.asyncio
async def test_broker_normalizes_success_timeout_and_crash() -> None:
    success = ExecutionBroker({Engine.PROLOG: FakeWorker()})
    assert (await success.execute(ExecutionRequest(engine=Engine.PROLOG, program=""))).status == ResultStatus.ANSWERED
    timeout = ExecutionBroker({Engine.PROLOG: FakeWorker(behavior="timeout")})
    assert (await timeout.execute(ExecutionRequest(engine=Engine.PROLOG, program="", timeout_seconds=0.01))).status == ResultStatus.TIMEOUT
    crash = ExecutionBroker({Engine.PROLOG: FakeWorker(behavior="crash")})
    assert (await crash.execute(ExecutionRequest(engine=Engine.PROLOG, program=""))).status == ResultStatus.ERROR


def test_router_selects_capabilities_and_rejects_cycles() -> None:
    health = tuple(EngineHealth(engine=engine, available=True) for engine in Engine)
    request = QueryRequest(goal=Atom(predicate="schedule"), capabilities=(Capability.CONSTRAINT, Capability.PLANNING))
    route = RoutingPolicy().route(request, health)
    assert [step.engine for step in route.steps] == [Engine.Z3, Engine.CLINGO]
    cycle = RoutingProposal(steps=(RoutingStep(id="one", engine=Engine.PROLOG, capability=Capability.RELATIONAL, depends_on=("two",)), RoutingStep(id="two", engine=Engine.PROLOG, capability=Capability.RELATIONAL, depends_on=("one",))), rationale="bad")
    with pytest.raises(ValueError, match="cycle"):
        RoutingPolicy().route(request, health, cycle)
