from __future__ import annotations

from pathlib import Path

import pytest

from compreditor.app import create_app
from compreditor.services.repository import WorkspaceRepository


CORPUS = """<?xml version='1.0' encoding='utf-8'?>
<document filename="DEMO.txt">
  <block id="1_DEMO" header="kamu nusi">
    <comment raw="IP-MAT,0@神主,*" />
    <IP-MAT><NP><N phon="LOG" form="kamu" /><N phon="LOG" form="nusi" lemma="L000002" /></NP></IP-MAT>
  </block>
</document>
"""

DICTIONARY = """<?xml version='1.0' encoding='utf-8'?>
<dictionary version="1.0">
  <entry id="L000002"><gloss>master</gloss><forms><form phonemic="nusi" kana="ヌシ" /></forms><pos><value>noun</value></pos></entry>
</dictionary>
"""


@pytest.fixture()
def editor(tmp_path: Path):
    source = tmp_path / "source"
    for folder in ("text", "trees", "dict"):
        (source / folder).mkdir(parents=True)
    (source / "text" / "DEMO.xml").write_text(CORPUS, encoding="utf-8")
    (source / "dict" / "dictionary.xml").write_text(DICTIONARY, encoding="utf-8")
    repository = WorkspaceRepository(source, tmp_path / "workspace")
    app = create_app(repository)
    app.config["TESTING"] = True
    return app.test_client(), repository, source


def test_outline_and_layer_payload(editor):
    client, _, _ = editor
    outline = client.get("/api/outline").get_json()
    assert outline[0]["families"][0]["documents"][0]["name"] == "DEMO.xml"
    payload = client.get("/api/documents/text/DEMO.xml").get_json()
    assert payload["tree"]["layer"] == "document"
    assert payload["sentences"][0]["id"] == "1_DEMO"
    assert [word["form"] for word in payload["words"]] == ["kamu", "nusi"]


def test_node_edit_is_overlay_only(editor):
    client, repository, source = editor
    source_before = (source / "text" / "DEMO.xml").read_bytes()
    response = client.post("/api/documents/text/DEMO.xml/nodes", json={
        "operation": "update",
        "path": "0.1.0.0",
        "tag": "N",
        "attributes": {"phon": "LOG", "form": "kami", "lemma": "L000002"},
    })
    assert response.status_code == 200
    assert repository.overlay_path("text", "DEMO.xml").is_file()
    assert (source / "text" / "DEMO.xml").read_bytes() == source_before
    assert response.get_json()["words"][0]["form"] == "kami"


def test_insert_copy_move_delete_and_raw_validation(editor):
    client, _, _ = editor
    added = client.post("/api/documents/text/DEMO.xml/nodes", json={
        "operation": "add", "path": "0.1.0", "tag": "N", "attributes": {"form": "ra", "phon": "LOG"},
    })
    assert added.status_code == 200
    reparented = client.post("/api/documents/text/DEMO.xml/nodes", json={
        "operation": "reparent", "path": added.get_json()["selected_path"], "target_path": "0.1",
    })
    assert reparented.status_code == 200
    selected = reparented.get_json()["selected_path"]
    moved = client.post("/api/documents/text/DEMO.xml/nodes", json={"operation": "move", "path": selected, "direction": "up"})
    assert moved.status_code == 200
    pasted = client.post("/api/documents/text/DEMO.xml/nodes", json={
        "operation": "paste", "path": "0.1.0", "node": {"tag": "N", "attributes": {"form": "copy", "phon": "LOG"}, "children": []},
    })
    assert pasted.status_code == 200
    deleted = client.post("/api/documents/text/DEMO.xml/nodes", json={"operation": "delete", "path": pasted.get_json()["selected_path"]})
    assert deleted.status_code == 200
    invalid = client.put("/api/documents/text/DEMO.xml/raw", data="<document><block>")
    assert invalid.status_code == 422
    assert invalid.get_json()["problems"][0]["code"] == "xml"


def test_dictionary_crud_and_lemma_generation_are_isolated(editor):
    client, repository, source = editor
    source_before = (source / "dict" / "dictionary.xml").read_bytes()
    suggestion = client.get("/api/dictionary/suggest-id?form=kamu&start=2").get_json()
    assert suggestion["id"] == "L000003"
    created = client.post("/api/dictionary", json=suggestion)
    assert created.status_code == 201
    assert repository.dictionary_overlay.is_file()
    assert (source / "dict" / "dictionary.xml").read_bytes() == source_before
    updated = client.put("/api/dictionary/L000003", json={
        "fields": [{"tag": ".FORM", "values": ["kamu"]}, {"tag": ".POS", "values": ["noun"]}],
    })
    assert updated.status_code == 200
    assert client.get("/api/dictionary/candidates?form=kamu").get_json()[0]["id"] == "L000003"
    assert client.delete("/api/dictionary/L000003").status_code == 200


def test_basic_advanced_and_structure_search(editor):
    client, _, _ = editor
    basic = client.post("/api/search", json={"query": "kamu", "scope": "text"}).get_json()
    assert any(result.get("form") == "kamu" for result in basic)
    advanced = client.post("/api/search", json={
        "scope": "text",
        "logic": "all",
        "structure": "NP > N",
        "criteria": [
            {"field": "phon", "operator": "equals", "value": "LOG"},
            {"field": "form", "operator": "contains", "value": "nusi", "exclude": True},
        ],
    }).get_json()
    assert [result["form"] for result in advanced] == ["kamu"]


def test_document_create_delete_uses_tombstones(editor):
    client, _, source = editor
    created = client.post("/api/documents", json={"collection": "text", "name": "NEW.xml"})
    assert created.status_code == 201
    assert client.delete("/api/documents/text/DEMO.xml").status_code == 200
    assert (source / "text" / "DEMO.xml").is_file()
    assert client.get("/api/documents/text/DEMO.xml").status_code == 404
