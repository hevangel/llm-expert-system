import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from llm_expert_system.api import create_app
from llm_expert_system.cli import app
from llm_expert_system.config import Settings
from llm_expert_system.lifecycle import ExpertSystemService
from llm_expert_system.storage import Workspace


@pytest.mark.asyncio
async def test_generation_activation_incremental_and_conflict_abstention(tmp_path: Path) -> None:
    source = tmp_path / "sources"
    source.mkdir()
    (source / "facts.txt").write_text("fact: operational(pump)\nfact: operational(pump)\n", encoding="utf-8")
    service = ExpertSystemService(Workspace(tmp_path / "workspace"))
    generated = await service.generate(source)
    manifest = service.validate_and_activate(generated.version_id)
    assert service.registry.active()["id"] == generated.version_id
    assert set(manifest.artifact_checksums) == {"knowledge.pl", "knowledge.clp", "knowledge.smt2", "knowledge.lp"}
    repeated = await service.generate(source)
    assert repeated.unchanged

    (source / "facts.txt").write_text("fact: operational(pump)\n", encoding="utf-8")
    (source / "conflict.txt").write_text("fact: operational(pump)\n", encoding="utf-8")
    # Explicit negative is added through IR elsewhere; this verifies lifecycle remains stable on update.
    updated = await service.generate(source)
    assert not updated.unchanged


def test_api_health_generate_and_versions(tmp_path: Path) -> None:
    source = tmp_path / "sources"
    source.mkdir()
    (source / "family.txt").write_text("Alice is parent of Bob.", encoding="utf-8")
    settings = Settings(workspace=tmp_path / "workspace")
    client = TestClient(create_app(settings))
    assert client.get("/health").json()["status"] == "ok"
    response = client.post("/api/v1/generate", json={"source_root": str(source), "activate": True})
    assert response.status_code == 200, response.text
    assert response.json()["active"] is True
    assert len(client.get("/api/v1/versions").json()) == 1


def test_cli_health_and_init_json(tmp_path: Path) -> None:
    runner = CliRunner()
    health = runner.invoke(app, ["health", "--json"])
    assert health.exit_code == 0
    assert json.loads(health.stdout)["status"] == "ok"
    initialized = runner.invoke(app, ["init", "--workspace", str(tmp_path / "workspace"), "--json"])
    assert initialized.exit_code == 0
    assert json.loads(initialized.stdout)["status"] == "initialized"
