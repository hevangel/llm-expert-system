"""FastAPI adapter for the shared expert-system application service."""

from __future__ import annotations

import hmac
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .config import Settings, get_settings
from .lifecycle import ExpertSystemService
from .models import ArtifactManifest, KnowledgeBase, QueryRequest, ReasoningResult
from .providers import FakeProvider, LiteLLMProvider
from .storage import Workspace


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateRequest(ApiModel):
    source_root: Path
    activate: bool = True


class GenerateResponse(ApiModel):
    version_id: str
    unchanged: bool
    active: bool
    manifest: ArtifactManifest | None = None


class RollbackRequest(ApiModel):
    version_id: str


class ResolveConflictRequest(ApiModel):
    accepted_item_ids: tuple[str, ...] = Field(min_length=1)
    note: str = Field(min_length=1, max_length=1000)
    activate: bool = True


class HealthResponse(ApiModel):
    status: str
    version: str


@lru_cache(maxsize=1)
def get_service() -> ExpertSystemService:
    settings = get_settings()
    provider = (
        FakeProvider()
        if settings.provider == "fake"
        else LiteLLMProvider(settings.model)
    )
    return ExpertSystemService(Workspace(settings.workspace), provider=provider)


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()
    configured.validate_security()
    application = FastAPI(
        title="LLM Expert System API",
        version=__version__,
        description="Generate and query safe, provenance-aware symbolic expert systems.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def service_dependency() -> ExpertSystemService:
        if settings is not None:
            provider = (
                FakeProvider()
                if configured.provider == "fake"
                else LiteLLMProvider(configured.model)
            )
            return ExpertSystemService(Workspace(configured.workspace), provider=provider)
        return get_service()

    def authorize_dependency(authorization: str | None = Header(default=None)) -> None:
        if not configured.api_token:
            return
        expected = f"Bearer {configured.api_token}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
            )

    @application.get("/health", response_model=HealthResponse, tags=["operations"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @application.get("/ready", tags=["operations"])
    def readiness(
        service: ExpertSystemService = Depends(service_dependency),
    ) -> dict[str, object]:
        return service.diagnostics()

    @application.post(
        "/api/v1/generate",
        response_model=GenerateResponse,
        dependencies=[Depends(authorize_dependency)],
        tags=["lifecycle"],
    )
    async def generate(
        body: GenerateRequest,
        service: ExpertSystemService = Depends(service_dependency),
    ) -> GenerateResponse:
        if not body.source_root.exists() or not body.source_root.is_dir():
            raise HTTPException(status_code=400, detail="source_root must be an existing directory")
        try:
            result = await service.generate(body.source_root, configured.max_source_bytes)
            manifest = None
            if body.activate and not result.unchanged:
                manifest = service.validate_and_activate(result.version_id)
            active = service.registry.active()
            return GenerateResponse(
                version_id=result.version_id,
                unchanged=result.unchanged,
                active=bool(active and active["id"] == result.version_id),
                manifest=manifest,
            )
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.get(
        "/api/v1/versions", dependencies=[Depends(authorize_dependency)], tags=["lifecycle"]
    )
    def versions(
        service: ExpertSystemService = Depends(service_dependency),
    ) -> list[dict[str, object]]:
        return service.registry.list()

    @application.get(
        "/api/v1/versions/{version_id}/knowledge",
        response_model=KnowledgeBase,
        dependencies=[Depends(authorize_dependency)],
        tags=["lifecycle"],
    )
    def knowledge(
        version_id: str,
        service: ExpertSystemService = Depends(service_dependency),
    ) -> KnowledgeBase:
        try:
            return service.registry.load_knowledge(version_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="version not found") from error

    @application.post(
        "/api/v1/rollback", dependencies=[Depends(authorize_dependency)], tags=["lifecycle"]
    )
    def rollback(
        body: RollbackRequest,
        service: ExpertSystemService = Depends(service_dependency),
    ) -> dict[str, str]:
        try:
            service.registry.rollback(body.version_id)
            return {"active_version": body.version_id}
        except KeyError as error:
            raise HTTPException(status_code=404, detail="version not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @application.get(
        "/api/v1/conflicts",
        dependencies=[Depends(authorize_dependency)],
        tags=["lifecycle"],
    )
    def conflicts(
        service: ExpertSystemService = Depends(service_dependency),
    ) -> list[dict[str, object]]:
        active = service.registry.active()
        if active is None:
            return []
        knowledge_base = service.registry.load_knowledge(active["id"])
        return [item.model_dump(mode="json") for item in knowledge_base.conflicts]

    @application.post(
        "/api/v1/conflicts/{conflict_id}/resolve",
        response_model=GenerateResponse,
        dependencies=[Depends(authorize_dependency)],
        tags=["lifecycle"],
    )
    def resolve_conflict(
        conflict_id: str,
        body: ResolveConflictRequest,
        service: ExpertSystemService = Depends(service_dependency),
    ) -> GenerateResponse:
        try:
            generated = service.resolve_conflict(conflict_id, body.accepted_item_ids, body.note)
            manifest = service.validate_and_activate(generated.version_id) if body.activate else None
            return GenerateResponse(
                version_id=generated.version_id,
                unchanged=False,
                active=body.activate,
                manifest=manifest,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail="conflict not found") from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @application.post(
        "/api/v1/query",
        response_model=ReasoningResult,
        dependencies=[Depends(authorize_dependency)],
        tags=["reasoning"],
    )
    async def query(
        body: QueryRequest,
        service: ExpertSystemService = Depends(service_dependency),
    ) -> ReasoningResult:
        return await service.query(body)

    static_candidates = (
        Path.cwd() / "web" / "dist",
        Path(__file__).resolve().parents[2] / "web" / "dist",
    )
    static_root = next((candidate for candidate in static_candidates if candidate.is_dir()), None)
    if static_root is not None:
        application.mount("/", StaticFiles(directory=static_root, html=True), name="web")

    return application


app = create_app()
