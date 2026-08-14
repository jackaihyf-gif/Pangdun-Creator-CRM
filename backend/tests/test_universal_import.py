from backend.app.database import SessionLocal
from backend.app.models import Campaign, Contact, ImportBatch, Media, Product, Project
from backend.app.universal_importer import STANDARD_HEADERS


def test_standard_csv_preview_confirm_and_undo(client, seeded_collaboration):
    headers = seeded_collaboration["headers"]
    values = [
        "Import Creator", "加拿大", "YouTube", "https://www.youtube.com/@importcreator", "科技", "125",
        "Alex", "商务", "alex@example.test", "+1 555 0100", "洽谈中", "IMPORT-001", "Import Launch",
        "admin@example.test", "长视频", "待发货", "2026-09-01", "确认收件信息", "2026-08-20",
        "MAXSUN B760M；MAXSUN RTX 5070", "PI-001", "DHL", "TRACK-001", "2026-08-14", "", "", "",
        "1000", "800", "USD", "未付款", "standard csv test",
    ]
    csv_bytes = (",".join(STANDARD_HEADERS) + "\n" + ",".join(values) + "\n").encode("utf-8")
    preview = client.post("/api/universal-import/preview", headers=headers, files={"file": ("standard.csv", csv_bytes, "text/csv")})
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["parser"] == "local_standard"
    assert payload["total"] == 1
    assert payload["created_count"] == 1
    assert payload["conflict_count"] == 0

    confirmed = client.post(f"/api/universal-import/{payload['draft_id']}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["success_count"] == 1
    with SessionLocal() as db:
        media = db.query(Media).filter(Media.name == "Import Creator").one()
        assert db.query(Contact).filter(Contact.media_id == media.id, Contact.email == "alex@example.test").count() == 1
        assert db.query(Project).filter(Project.project_code == "IMPORT-001").count() == 1
        assert db.query(Campaign).filter(Campaign.media_id == media.id).count() == 1
        assert db.query(Product).filter(Product.model == "MAXSUN B760M").count() == 1

    undone = client.post(f"/api/import-batches/{result['batch_id']}/undo", headers=headers)
    assert undone.status_code == 200, undone.text
    with SessionLocal() as db:
        assert db.query(Media).filter(Media.name == "Import Creator").count() == 0
        assert db.query(Project).filter(Project.project_code == "IMPORT-001").count() == 0


def test_template_download_has_bom_and_standard_headers(client, seeded_collaboration):
    response = client.get("/api/universal-import/template.csv", headers=seeded_collaboration["headers"])
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert "媒体名称*" in response.content.decode("utf-8-sig")


def test_nonstandard_csv_uses_agent_only_for_header_mapping(client, seeded_collaboration, monkeypatch):
    calls = []

    def fake_agent(system_prompt, user_prompt, **kwargs):
        calls.append((system_prompt, user_prompt))
        return {"mapping": {"Creator": "media_name", "Country": "country", "Page": "profile_url", "Email": "contact_email"}, "warnings": []}, {"total_tokens": 42}

    monkeypatch.setattr("backend.app.universal_importer.deepseek_json_object", fake_agent)
    content = b"Creator,Country,Page,Email\nMapped Creator,US,https://youtube.com/@mapped,mapped@example.test\n"
    response = client.post("/api/universal-import/preview", headers=seeded_collaboration["headers"], files={"file": ("other.csv", content, "text/csv")})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["parser"] == "agent_mapping"
    assert payload["mapping"]["Creator"] == "media_name"
    assert len(calls) == 1
    assert "Mapped Creator" in calls[0][1]
