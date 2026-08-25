import json
from pathlib import Path

import pytest

from llm_expert_system.ingestion import DocumentIngester, IngestionError


def test_imports_supported_formats_with_locators(tmp_path: Path) -> None:
    (tmp_path / "facts.md").write_text("# Facts\n\nAlice is parent of Bob.\n", encoding="utf-8")
    (tmp_path / "data.json").write_text(json.dumps({"people": ["Alice", "Bob"]}), encoding="utf-8")
    documents = DocumentIngester(tmp_path).import_directory()
    assert len(documents) == 2
    assert any(section.locator.startswith("lines:") for document in documents for section in document.sections)
    assert any(section.locator == "$/people/0" for document in documents for section in document.sections)


def test_rejects_escape_malformed_and_oversized(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    with pytest.raises(IngestionError, match="escapes"):
        DocumentIngester(tmp_path).import_file(outside)
    malformed = tmp_path / "bad.yaml"
    malformed.write_text("key: [", encoding="utf-8")
    with pytest.raises(IngestionError, match="malformed"):
        DocumentIngester(tmp_path).import_file(malformed)
    large = tmp_path / "large.txt"
    large.write_text("abcdef", encoding="utf-8")
    with pytest.raises(IngestionError, match="exceeds"):
        DocumentIngester(tmp_path, max_bytes=3).import_file(large)


def test_deduplicates_identical_content(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("same", encoding="utf-8")
    (tmp_path / "b.txt").write_text("same", encoding="utf-8")
    assert len(DocumentIngester(tmp_path).import_directory()) == 1
