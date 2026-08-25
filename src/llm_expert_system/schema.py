"""Schema export utility used by CI to detect contract drift."""

import json
from pathlib import Path

from .models import KnowledgeBase, QueryRequest, ReasoningResult


def export_schemas(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    schemas = {
        "knowledge-base.schema.json": KnowledgeBase.model_json_schema(),
        "query-request.schema.json": QueryRequest.model_json_schema(),
        "reasoning-result.schema.json": ReasoningResult.model_json_schema(),
    }
    for name, schema in schemas.items():
        (destination / name).write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
