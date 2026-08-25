"""Bounded common execution broker for local and container workers."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .models import Engine, ReasoningResult, ResultStatus


@dataclass(frozen=True)
class ExecutionRequest:
    engine: Engine
    program: str
    query: str = ""
    timeout_seconds: float = 10
    max_output_bytes: int = 1_000_000
    max_models: int = 10


class EngineWorker(Protocol):
    engine: Engine
    def execute(self, request: ExecutionRequest) -> ReasoningResult: ...


class FakeWorker:
    def __init__(self, engine: Engine = Engine.PROLOG, behavior: str = "success") -> None:
        self.engine = engine
        self.behavior = behavior

    def execute(self, request: ExecutionRequest) -> ReasoningResult:
        import time
        if self.behavior == "crash":
            raise RuntimeError("simulated worker crash")
        if self.behavior == "timeout":
            time.sleep(request.timeout_seconds * 2)
        return ReasoningResult(
            status=ResultStatus.ANSWERED,
            engine=self.engine,
            diagnostics=("fake worker",),
        )


class ExecutionBroker:
    """Concurrency and timeout boundary; container mode is the security boundary."""

    def __init__(self, workers: Mapping[Engine, EngineWorker], concurrency: int = 4) -> None:
        self.workers = dict(workers)
        self._semaphore = asyncio.Semaphore(concurrency)

    async def execute(self, request: ExecutionRequest) -> ReasoningResult:
        worker = self.workers.get(request.engine)
        if worker is None:
            return ReasoningResult(
                status=ResultStatus.ERROR,
                engine=request.engine,
                diagnostics=("engine worker unavailable",),
            )
        async with self._semaphore:
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(worker.execute, request), timeout=request.timeout_seconds
                )
                encoded = result.model_dump_json().encode()
                if len(encoded) > request.max_output_bytes:
                    return ReasoningResult(
                        status=ResultStatus.ERROR,
                        engine=request.engine,
                        diagnostics=("engine output exceeded configured limit",),
                    )
                return result
            except TimeoutError:
                return ReasoningResult(
                    status=ResultStatus.TIMEOUT,
                    engine=request.engine,
                    diagnostics=("engine request timed out",),
                )
            except Exception as error:
                return ReasoningResult(
                    status=ResultStatus.ERROR,
                    engine=request.engine,
                    diagnostics=(f"engine worker failed: {type(error).__name__}",),
                )
