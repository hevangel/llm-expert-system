from pathlib import Path

import pytest

from llm_expert_system.models import ArtifactManifest, Engine, KnowledgeBase, VersionState
from llm_expert_system.storage import VersionRegistry, Workspace


def advance_to_consistent(registry: VersionRegistry, version_id: str) -> None:
    for state in (VersionState.IR_VALIDATED, VersionState.RENDERED, VersionState.SYNTAX_CHECKED, VersionState.SEMANTIC_CHECKED, VersionState.CONSISTENCY_CHECKED):
        registry.transition(version_id, state)


def test_version_activation_immutability_and_rollback(tmp_path: Path) -> None:
    registry = VersionRegistry(Workspace(tmp_path / "workspace"))
    first = registry.create_draft(KnowledgeBase())
    advance_to_consistent(registry, first)
    manifest = ArtifactManifest(version_id=first, knowledge_digest=KnowledgeBase().digest, schema_version="1.0", source_hashes={}, provider="fake", model="fake", renderer_versions={engine: "1" for engine in Engine})
    registry.finalize(first, manifest)
    registry.activate(first)
    second = registry.create_draft(KnowledgeBase(entities=()))
    assert second != first
    advance_to_consistent(registry, second)
    manifest2 = manifest.model_copy(update={"version_id": second})
    registry.finalize(second, manifest2)
    registry.activate(second)
    assert registry.get(first)["state"] == VersionState.SUPERSEDED
    registry.rollback(first)
    assert registry.active()["id"] == first
    with pytest.raises(ValueError):
        registry.write_artifact(first, "late.txt", "no")


def test_workspace_rejects_path_escape(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    workspace.initialize()
    with pytest.raises(ValueError, match="escapes"):
        workspace.safe_path(tmp_path / "outside")
