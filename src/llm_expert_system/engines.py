"""Native engine health, validation, and execution adapters."""

from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from .broker import EngineWorker, ExecutionRequest
from .models import Engine, EngineHealth, ReasoningResult, ResultStatus


class PrologWorker:
    engine = Engine.PROLOG

    @staticmethod
    def health() -> EngineHealth:
        executable = shutil.which("swipl")
        if not executable:
            return EngineHealth(engine=Engine.PROLOG, available=False, detail="swipl not on PATH")
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, timeout=5, check=False
        )
        return EngineHealth(engine=Engine.PROLOG, available=result.returncode == 0, version=result.stdout.strip())

    def execute(self, request: ExecutionRequest) -> ReasoningResult:
        if not shutil.which("swipl"):
            raise RuntimeError("SWI-Prolog is unavailable")
        from swiplserver import PrologMQI  # type: ignore[import-untyped]

        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / "knowledge.pl"
            program.write_text(request.program, encoding="utf-8")
            escaped_path = program.as_posix().replace("'", "\\'")
            with PrologMQI() as mqi, mqi.create_thread() as prolog:
                loaded = prolog.query(
                    f"consult('{escaped_path}')",
                    query_timeout_seconds=request.timeout_seconds,
                )
                if loaded is False:
                    return ReasoningResult(
                        status=ResultStatus.ERROR,
                        engine=self.engine,
                        diagnostics=("generated Prolog failed to load",),
                    )
                answer = prolog.query(
                    request.query or "true",
                    query_timeout_seconds=request.timeout_seconds,
                )
        if answer is False:
            return ReasoningResult(status=ResultStatus.UNKNOWN, engine=self.engine)
        bindings = tuple(item for item in answer if isinstance(item, dict)) if isinstance(answer, list) else ()
        return ReasoningResult(
            status=ResultStatus.ANSWERED,
            engine=self.engine,
            bindings=bindings,
        )


class ClipsWorker:
    engine = Engine.CLIPS

    @staticmethod
    def health() -> EngineHealth:
        try:
            version = importlib.metadata.version("clipspy")
            return EngineHealth(engine=Engine.CLIPS, available=True, version=version)
        except importlib.metadata.PackageNotFoundError:
            return EngineHealth(engine=Engine.CLIPS, available=False, detail="clipspy not installed")

    def execute(self, request: ExecutionRequest) -> ReasoningResult:
        import clips  # type: ignore[import-untyped]
        environment = clips.Environment()
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / "knowledge.clp"
            program.write_text(request.program, encoding="utf-8")
            environment.load(str(program))
        environment.reset()
        fired = environment.run(10_000)
        facts = tuple(tuple(str(fact).split()) for fact in environment.facts())
        return ReasoningResult(
            status=ResultStatus.ANSWERED,
            engine=self.engine,
            models=facts[: request.max_models],
            diagnostics=(f"rules fired: {fired}",),
        )


class Z3Worker:
    engine = Engine.Z3

    @staticmethod
    def health() -> EngineHealth:
        try:
            version = importlib.metadata.version("z3-solver")
            return EngineHealth(engine=Engine.Z3, available=True, version=version)
        except importlib.metadata.PackageNotFoundError:
            return EngineHealth(engine=Engine.Z3, available=False, detail="z3-solver not installed")

    def execute(self, request: ExecutionRequest) -> ReasoningResult:
        import z3  # type: ignore[import-untyped]
        solver = z3.Solver()
        solver.set(timeout=int(request.timeout_seconds * 1000))
        assertions = z3.parse_smt2_string(
            request.program.replace("(check-sat)", "").replace("(get-model)", "")
        )
        solver.add(assertions)
        outcome = solver.check()
        if outcome == z3.sat:
            model = solver.model()
            bindings = ({str(item): str(model[item]) for item in model},)
            return ReasoningResult(status=ResultStatus.ANSWERED, engine=self.engine, bindings=bindings)
        if outcome == z3.unsat:
            return ReasoningResult(status=ResultStatus.UNSAT, engine=self.engine)
        return ReasoningResult(status=ResultStatus.UNKNOWN, engine=self.engine, diagnostics=(solver.reason_unknown(),))


class ClingoWorker:
    engine = Engine.CLINGO

    @staticmethod
    def health() -> EngineHealth:
        try:
            version = importlib.metadata.version("clingo")
            return EngineHealth(engine=Engine.CLINGO, available=True, version=version)
        except importlib.metadata.PackageNotFoundError:
            return EngineHealth(engine=Engine.CLINGO, available=False, detail="clingo not installed")

    def execute(self, request: ExecutionRequest) -> ReasoningResult:
        import clingo
        control = clingo.Control([str(request.max_models)])
        control.add("base", [], request.program)
        control.ground([("base", [])])
        models: list[tuple[str, ...]] = []
        with control.solve(yield_=True) as handle:
            for model in handle:
                models.append(tuple(sorted(str(symbol) for symbol in model.symbols(shown=True))))
                if len(models) >= request.max_models:
                    handle.cancel()
                    break
            result = handle.get()
        if models:
            return ReasoningResult(status=ResultStatus.ANSWERED, engine=self.engine, models=tuple(models))
        status = ResultStatus.UNSAT if result.unsatisfiable else ResultStatus.UNKNOWN
        return ReasoningResult(status=status, engine=self.engine)


class NativeEngineWorker(EngineWorker, Protocol):
    @staticmethod
    def health() -> EngineHealth: ...


WORKERS: dict[Engine, NativeEngineWorker] = {
    Engine.PROLOG: PrologWorker(),
    Engine.CLIPS: ClipsWorker(),
    Engine.Z3: Z3Worker(),
    Engine.CLINGO: ClingoWorker(),
}


def engine_health() -> tuple[EngineHealth, ...]:
    return tuple(worker.health() for worker in WORKERS.values())
