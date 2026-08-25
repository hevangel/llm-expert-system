from pathlib import Path

import pytest

from llm_expert_system.ingestion import DocumentIngester
from llm_expert_system.providers import FakeProvider


@pytest.mark.asyncio
async def test_fake_provider_is_deterministic_and_preserves_evidence(tmp_path: Path) -> None:
    source = tmp_path / "family.txt"
    source.write_text("Alice is parent of Bob.\nfact: likes(bob, chess)\n", encoding="utf-8")
    document = DocumentIngester(tmp_path).import_file(source)
    provider = FakeProvider()
    first = await provider.extract(document)
    second = await provider.extract(document)
    assert first.knowledge.digest == second.knowledge.digest
    assert [fact.atom.predicate for fact in first.knowledge.facts] == ["parent", "likes"]
    assert all(fact.evidence for fact in first.knowledge.facts)
