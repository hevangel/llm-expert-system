"""Safe local document ingestion with precise provenance locators."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .models import SourceDocument, SourceSection

_MEDIA_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
}


class IngestionError(ValueError):
    pass


class DocumentIngester:
    def __init__(self, import_root: Path, max_bytes: int = 1_048_576) -> None:
        self.import_root = import_root.expanduser().resolve()
        self.max_bytes = max_bytes

    def import_file(self, path: Path) -> SourceDocument:
        requested = path if path.is_absolute() else self.import_root / path
        if requested.is_symlink():
            raise IngestionError("symbolic links are not accepted")
        resolved = requested.resolve(strict=True)
        if not resolved.is_relative_to(self.import_root):
            raise IngestionError("source path escapes import root")
        if not resolved.is_file():
            raise IngestionError("source must be a regular file")
        suffix = resolved.suffix.lower()
        if suffix not in _MEDIA_TYPES:
            guessed = mimetypes.guess_type(resolved.name)[0]
            raise IngestionError(f"unsupported source type: {suffix or guessed or 'unknown'}")
        size = resolved.stat().st_size
        if size > self.max_bytes:
            raise IngestionError(f"source exceeds {self.max_bytes} bytes")
        raw = resolved.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise IngestionError("source must be UTF-8") from error
        digest = hashlib.sha256(raw).hexdigest()
        sections = self._sections(text, suffix)
        relative_path = resolved.relative_to(self.import_root).as_posix()
        return SourceDocument(
            id=f"doc-{digest[:20]}",
            relative_path=relative_path,
            media_type=_MEDIA_TYPES[suffix],  # type: ignore[arg-type]
            sha256=digest,
            imported_at=datetime.fromtimestamp(resolved.stat().st_mtime, UTC),
            sections=tuple(sections),
        )

    def import_directory(self, path: Path = Path(".")) -> tuple[SourceDocument, ...]:
        requested = (self.import_root / path).resolve() if not path.is_absolute() else path.resolve()
        if not requested.is_relative_to(self.import_root):
            raise IngestionError("directory escapes import root")
        documents: dict[str, SourceDocument] = {}
        for candidate in sorted(requested.rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in _MEDIA_TYPES:
                document = self.import_file(candidate)
                documents[document.sha256] = document
        return tuple(documents.values())

    def _sections(self, text: str, suffix: str) -> Iterable[SourceSection]:
        if suffix in {".json", ".yaml", ".yml"}:
            try:
                data = json.loads(text) if suffix == ".json" else yaml.safe_load(text)
            except (json.JSONDecodeError, yaml.YAMLError) as error:
                raise IngestionError(f"malformed structured document: {error}") from error
            if data is None:
                return ()
            return tuple(self._walk(data, "$"))
        lines = text.splitlines()
        sections: list[SourceSection] = []
        start = 0
        buffer: list[str] = []
        for index, line in enumerate(lines, start=1):
            if not line.strip() and buffer:
                body = "\n".join(buffer).strip()
                sections.append(self._text_section(start, index - 1, body))
                buffer = []
            elif line.strip():
                if not buffer:
                    start = index
                buffer.append(line)
        if buffer:
            sections.append(self._text_section(start, len(lines), "\n".join(buffer).strip()))
        return sections

    @staticmethod
    def _text_section(start: int, end: int, body: str) -> SourceSection:
        digest = hashlib.sha256(f"{start}:{end}:{body}".encode()).hexdigest()[:20]
        return SourceSection(id=f"section-{digest}", locator=f"lines:{start}-{end}", text=body)

    def _walk(self, value: Any, pointer: str) -> Iterable[SourceSection]:
        if isinstance(value, dict):
            for key in sorted(value, key=str):
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                yield from self._walk(value[key], f"{pointer}/{escaped}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from self._walk(item, f"{pointer}/{index}")
        else:
            text = json.dumps(value, ensure_ascii=False)
            digest = hashlib.sha256(f"{pointer}:{text}".encode()).hexdigest()[:20]
            yield SourceSection(id=f"section-{digest}", locator=pointer, text=text)
