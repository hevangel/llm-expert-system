"""SQLite metadata registry and immutable artifact workspace."""

from __future__ import annotations

import builtins
import hashlib
import json
import shutil
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import ArtifactManifest, KnowledgeBase, VersionState

_ALLOWED_TRANSITIONS: dict[VersionState, set[VersionState]] = {
    VersionState.DRAFT: {VersionState.IR_VALIDATED, VersionState.REJECTED},
    VersionState.IR_VALIDATED: {VersionState.RENDERED, VersionState.REJECTED},
    VersionState.RENDERED: {VersionState.SYNTAX_CHECKED, VersionState.REJECTED},
    VersionState.SYNTAX_CHECKED: {VersionState.SEMANTIC_CHECKED, VersionState.REJECTED},
    VersionState.SEMANTIC_CHECKED: {VersionState.CONSISTENCY_CHECKED, VersionState.REJECTED},
    VersionState.CONSISTENCY_CHECKED: {VersionState.STAGED, VersionState.REJECTED},
    VersionState.STAGED: {VersionState.ACTIVE, VersionState.REJECTED},
    VersionState.ACTIVE: {VersionState.SUPERSEDED},
    VersionState.SUPERSEDED: {VersionState.ACTIVE},
    VersionState.REJECTED: set(),
}


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.sources = self.root / "sources"
        self.staging = self.root / "staging"
        self.versions = self.root / "versions"
        self.logs = self.root / "logs"
        self.db_path = self.root / "registry.sqlite3"

    def initialize(self) -> None:
        for path in (self.root, self.sources, self.staging, self.versions, self.logs):
            path.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);
                CREATE TABLE IF NOT EXISTS versions(
                    id TEXT PRIMARY KEY, state TEXT NOT NULL, digest TEXT NOT NULL,
                    created_at TEXT NOT NULL, path TEXT, rejection_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS active_version(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), version_id TEXT,
                    FOREIGN KEY(version_id) REFERENCES versions(id)
                );
                INSERT OR IGNORE INTO active_version(singleton, version_id) VALUES (1, NULL);
                CREATE TABLE IF NOT EXISTS sources(
                    id TEXT PRIMARY KEY, relative_path TEXT NOT NULL, sha256 TEXT NOT NULL,
                    payload TEXT NOT NULL, imported_at TEXT NOT NULL,
                    UNIQUE(relative_path, sha256)
                );
                CREATE TABLE IF NOT EXISTS audit(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
                    subject TEXT, detail TEXT NOT NULL, created_at TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def safe_path(self, candidate: Path) -> Path:
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"path escapes workspace: {candidate}")
        return resolved

    def audit(self, event: str, subject: str | None, detail: dict[str, Any]) -> None:
        safe_detail = {key: value for key, value in detail.items() if "token" not in key.lower()}
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO audit(event, subject, detail, created_at) VALUES (?, ?, ?, ?)",
                (event, subject, json.dumps(safe_detail, sort_keys=True), datetime.now(UTC).isoformat()),
            )


class VersionRegistry:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.workspace.initialize()

    def create_draft(self, knowledge: KnowledgeBase) -> str:
        version_id = f"v-{knowledge.digest[:16]}-{uuid.uuid4().hex[:8]}"
        draft = self.workspace.safe_path(self.workspace.staging / version_id)
        draft.mkdir()
        (draft / "knowledge.json").write_text(knowledge.canonical_json(), encoding="utf-8")
        with self.workspace.connect() as connection:
            connection.execute(
                "INSERT INTO versions(id, state, digest, created_at, path) VALUES (?, ?, ?, ?, ?)",
                (version_id, VersionState.DRAFT, knowledge.digest, datetime.now(UTC).isoformat(), str(draft)),
            )
        self.workspace.audit("version.created", version_id, {"digest": knowledge.digest})
        return version_id

    def transition(self, version_id: str, target: VersionState, reason: str | None = None) -> None:
        record = self.get(version_id)
        current = VersionState(record["state"])
        if target not in _ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"invalid transition {current} -> {target}")
        with self.workspace.connect() as connection:
            connection.execute(
                "UPDATE versions SET state=?, rejection_reason=? WHERE id=?",
                (target, reason if target == VersionState.REJECTED else None, version_id),
            )
        self.workspace.audit("version.transition", version_id, {"from": current, "to": target, "reason": reason})

    def finalize(self, version_id: str, manifest: ArtifactManifest) -> Path:
        record = self.get(version_id)
        if VersionState(record["state"]) != VersionState.CONSISTENCY_CHECKED:
            raise ValueError("only consistency-checked versions can be finalized")
        source = self.workspace.safe_path(Path(record["path"]))
        destination = self.workspace.safe_path(self.workspace.versions / version_id)
        if destination.exists():
            raise FileExistsError(f"immutable version already exists: {version_id}")
        (source / "manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        source.replace(destination)
        with self.workspace.connect() as connection:
            connection.execute("UPDATE versions SET path=? WHERE id=?", (str(destination), version_id))
        self.transition(version_id, VersionState.STAGED)
        return destination

    def activate(self, version_id: str) -> None:
        record = self.get(version_id)
        if VersionState(record["state"]) not in {VersionState.STAGED, VersionState.SUPERSEDED}:
            raise ValueError("only staged or superseded versions can be activated")
        with self.workspace.connect() as connection:
            previous = connection.execute(
                "SELECT version_id FROM active_version WHERE singleton=1"
            ).fetchone()[0]
            if previous and previous != version_id:
                connection.execute(
                    "UPDATE versions SET state=? WHERE id=?", (VersionState.SUPERSEDED, previous)
                )
            connection.execute("UPDATE versions SET state=? WHERE id=?", (VersionState.ACTIVE, version_id))
            connection.execute(
                "UPDATE active_version SET version_id=? WHERE singleton=1", (version_id,)
            )
        self.workspace.audit("version.activated", version_id, {"previous": previous})

    def rollback(self, version_id: str) -> None:
        if VersionState(self.get(version_id)["state"]) != VersionState.SUPERSEDED:
            raise ValueError("rollback target must be a superseded version")
        self.activate(version_id)
        self.workspace.audit("version.rolled_back", version_id, {})

    def get(self, version_id: str) -> dict[str, Any]:
        with self.workspace.connect() as connection:
            row = connection.execute("SELECT * FROM versions WHERE id=?", (version_id,)).fetchone()
        if row is None:
            raise KeyError(version_id)
        return dict(row)

    def list(self) -> list[dict[str, Any]]:
        with self.workspace.connect() as connection:
            rows = connection.execute("SELECT * FROM versions ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def active(self) -> dict[str, Any] | None:
        with self.workspace.connect() as connection:
            row = connection.execute(
                "SELECT v.* FROM versions v JOIN active_version a ON v.id=a.version_id WHERE a.singleton=1"
            ).fetchone()
        return dict(row) if row else None

    def load_knowledge(self, version_id: str) -> KnowledgeBase:
        path = self.workspace.safe_path(Path(self.get(version_id)["path"]) / "knowledge.json")
        return KnowledgeBase.model_validate_json(path.read_text(encoding="utf-8"))

    def write_artifact(self, version_id: str, name: str, content: str) -> str:
        if Path(name).name != name:
            raise ValueError("artifact name must be a basename")
        record = self.get(version_id)
        if VersionState(record["state"]) not in {VersionState.DRAFT, VersionState.IR_VALIDATED}:
            raise ValueError("artifacts can only be written before rendering is complete")
        path = self.workspace.safe_path(Path(record["path"]) / name)
        path.write_text(content, encoding="utf-8", newline="\n")
        return hashlib.sha256(content.encode()).hexdigest()

    def export_version(self, version_id: str, destination: Path) -> Path:
        source = self.workspace.safe_path(Path(self.get(version_id)["path"]))
        destination = destination.expanduser().resolve()
        if destination.exists():
            raise FileExistsError(f"export destination exists: {destination}")
        shutil.copytree(source, destination)
        self.workspace.audit("version.exported", version_id, {"destination": str(destination)})
        return destination

    def reconcile(self) -> builtins.list[str]:
        recovered: builtins.list[str] = []
        with self.workspace.connect() as connection:
            rows = connection.execute("SELECT id, state, path FROM versions").fetchall()
        for row in rows:
            path = Path(row["path"]) if row["path"] else None
            if path and not path.exists() and row["state"] != VersionState.REJECTED:
                with self.workspace.connect() as connection:
                    connection.execute(
                        "UPDATE versions SET state=?, rejection_reason=? WHERE id=?",
                        (VersionState.REJECTED, "artifact directory missing during reconciliation", row["id"]),
                    )
                recovered.append(row["id"])
        for path in self.workspace.staging.iterdir():
            if path.is_dir() and not any(row["id"] == path.name for row in rows):
                shutil.rmtree(path)
                recovered.append(path.name)
        return recovered
