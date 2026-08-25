from pathlib import Path

from fastapi.testclient import TestClient

from llm_expert_system.api import create_app
from llm_expert_system.config import Settings


def test_api_authentication_conflict_abstention_and_resolution(tmp_path: Path) -> None:
    source = tmp_path / "sources"
    source.mkdir()
    (source / "conflict.txt").write_text(
        "fact: operational(pump_1)\nfact: !operational(pump_1)\n",
        encoding="utf-8",
    )
    settings = Settings(workspace=tmp_path / "workspace", api_token="secret")
    client = TestClient(create_app(settings))
    assert client.get("/api/v1/versions").status_code == 401
    headers = {"Authorization": "Bearer secret"}
    generated = client.post(
        "/api/v1/generate",
        json={"source_root": str(source), "activate": True},
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    conflicts = client.get("/api/v1/conflicts", headers=headers).json()
    assert len(conflicts) == 1
    query = client.post(
        "/api/v1/query",
        json={
            "goal": {"predicate": "operational", "arguments": ["pump_1"]},
            "capabilities": ["relational"],
        },
        headers=headers,
    )
    assert query.json()["status"] == "abstained"
    resolved = client.post(
        f"/api/v1/conflicts/{conflicts[0]['id']}/resolve",
        json={
            "accepted_item_ids": [conflicts[0]["item_ids"][0]],
            "note": "Accepted the first source assertion in a test review.",
            "activate": True,
        },
        headers=headers,
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["active"] is True
    updated = client.get("/api/v1/conflicts", headers=headers).json()
    assert updated[0]["resolved"] is True
