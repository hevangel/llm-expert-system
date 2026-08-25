"""Typer CLI adapter with human-readable and stable JSON output."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

from . import __version__
from .config import Settings
from .lifecycle import ExpertSystemService
from .models import Atom, Capability, QueryRequest
from .providers import FakeProvider, LiteLLMProvider
from .schema import export_schemas
from .storage import Workspace

app = typer.Typer(no_args_is_help=True, help="Generate and query symbolic expert systems.")


def _service(workspace: Path) -> ExpertSystemService:
    settings = Settings(workspace=workspace)
    provider = FakeProvider() if settings.provider == "fake" else LiteLLMProvider(settings.model)
    return ExpertSystemService(Workspace(settings.workspace), provider=provider)


def _emit(value: object, as_json: bool) -> None:
    if as_json:
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        typer.echo(json.dumps(value, indent=2, default=str))
    else:
        typer.echo(value)


@app.command()
def health(json_output: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Report CLI health and version."""
    _emit({"status": "ok", "version": __version__}, json_output)


@app.command()
def init(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Initialize a workspace and registry."""
    service = _service(workspace)
    _emit({"workspace": str(service.workspace.root), "status": "initialized"}, json_output)


@app.command()
def diagnostics(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Check registry and native engine availability."""
    _emit(_service(workspace).diagnostics(), json_output)


@app.command()
def generate(
    source: Annotated[Path, typer.Argument(help="Directory containing local source documents")],
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
    activate: Annotated[bool, typer.Option("--activate/--no-activate")] = True,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Ingest, synthesize, validate, and optionally activate a version."""
    service = _service(workspace)
    result = asyncio.run(service.generate(source))
    manifest = None
    if activate and not result.unchanged:
        manifest = service.validate_and_activate(result.version_id)
    active = service.registry.active()
    _emit(
        {
            "version_id": result.version_id,
            "unchanged": result.unchanged,
            "active": bool(active and active["id"] == result.version_id),
            "manifest": manifest.model_dump(mode="json") if manifest else None,
        },
        json_output,
    )


@app.command("versions")
def list_versions(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List immutable knowledge versions."""
    _emit(_service(workspace).registry.list(), json_output)


@app.command()
def query(
    predicate: Annotated[str, typer.Argument()],
    arguments: Annotated[list[str] | None, typer.Argument()] = None,
    capability: Annotated[Capability, typer.Option("--capability", "-c")] = Capability.RELATIONAL,
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
    timeout: Annotated[float, typer.Option("--timeout")] = 10,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Query the active expert-system version."""
    service = _service(workspace)
    result = asyncio.run(
        service.query(
            QueryRequest(
                goal=Atom(predicate=predicate, arguments=tuple(arguments or ())),
                capabilities=(capability,),
                timeout_seconds=timeout,
            )
        )
    )
    _emit(result, json_output)
    if result.status in {"error", "timeout"}:
        raise typer.Exit(code=2)
    if result.status == "abstained":
        raise typer.Exit(code=3)


@app.command()
def conflicts(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List conflicts in the active version."""
    service = _service(workspace)
    active = service.registry.active()
    knowledge = service.registry.load_knowledge(active["id"]) if active else None
    values = [item.model_dump(mode="json") for item in knowledge.conflicts] if knowledge else []
    _emit(values, json_output)


@app.command("resolve-conflict")
def resolve_conflict(
    conflict_id: Annotated[str, typer.Argument()],
    accept: Annotated[list[str], typer.Option("--accept")],
    note: Annotated[str, typer.Option("--note")],
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
) -> None:
    """Create and activate an audited conflict-resolution version."""
    service = _service(workspace)
    generated = service.resolve_conflict(conflict_id, tuple(accept), note)
    service.validate_and_activate(generated.version_id)
    typer.echo(generated.version_id)


@app.command("export")
def export_version(
    version_id: Annotated[str, typer.Argument()],
    destination: Annotated[Path, typer.Argument()],
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
) -> None:
    """Export one immutable artifact directory."""
    typer.echo(_service(workspace).registry.export_version(version_id, destination))


@app.command()
def rollback(
    version_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
) -> None:
    """Reactivate a superseded last-known-good version."""
    service = _service(workspace)
    service.registry.rollback(version_id)
    typer.echo(version_id)


@app.command("export-schema")
def export_schema(
    destination: Annotated[Path, typer.Option("--destination", "-d")] = Path("schemas"),
) -> None:
    """Export canonical JSON schemas."""
    export_schemas(destination)
    typer.echo(destination)


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
    workspace: Annotated[Path, typer.Option("--workspace", "-w")] = Path(".llm-expert"),
) -> None:
    """Run the API server. Use this command manually; it is long-running."""
    import uvicorn

    from .api import create_app

    settings = Settings(workspace=workspace, api_host=host, api_port=port)
    settings.validate_security()
    uvicorn.run(create_app(settings), host=host, port=port)
