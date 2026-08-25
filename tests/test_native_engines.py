from llm_expert_system.broker import ExecutionRequest
from llm_expert_system.engines import ClingoWorker, ClipsWorker, Z3Worker
from llm_expert_system.models import Engine, ResultStatus


def test_clips_loads_and_runs_generated_program() -> None:
    program = '(deffacts initial (temperature "hot"))\n(defrule alert (temperature "hot") => (assert (alarm "on")))\n'
    result = ClipsWorker().execute(ExecutionRequest(engine=Engine.CLIPS, program=program))
    assert result.status == ResultStatus.ANSWERED
    assert any("alarm" in " ".join(model) for model in result.models)


def test_z3_reports_sat_and_model() -> None:
    program = "(set-logic ALL)\n(declare-const load Int)\n(assert (<= load 10))\n(check-sat)\n(get-model)\n"
    result = Z3Worker().execute(ExecutionRequest(engine=Engine.Z3, program=program))
    assert result.status == ResultStatus.ANSWERED


def test_clingo_enumerates_answer_sets() -> None:
    program = 'parent("alice", "bob").\nancestor(X,Y) :- parent(X,Y).\n#show ancestor/2.\n'
    result = ClingoWorker().execute(ExecutionRequest(engine=Engine.CLINGO, program=program))
    assert result.status == ResultStatus.ANSWERED
    assert any('ancestor("alice","bob")' in model for model in result.models)
