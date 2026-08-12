from backend.app.database import SessionLocal
from backend.app.models import Activity, Campaign, Shipment


def test_collaboration_patch_saves_follow_up_and_shipment(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    response = client.patch(
        f"/api/collaborations/{campaign_id}",
        headers=seeded_collaboration["headers"],
        json={
            "execution_status": "运输中",
            "next_action": "跟踪物流并确认到达时间",
            "follow_up_date": "2026-08-18",
            "follow_up_priority": "高",
            "oa_pi_number": "OA-TEST-100",
            "tracking_number": "TRACK-TEST-200",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_status"] == "运输中"
    assert payload["next_action"] == "跟踪物流并确认到达时间"
    assert payload["follow_up_date"] == "2026-08-18"
    assert payload["follow_up_priority"] == "高"
    assert payload["oa_pi_number"] == "OA-TEST-100"
    assert payload["tracking_number"] == "TRACK-TEST-200"
    assert payload["workflow_health"] == "ready"
    assert payload["workflow_warnings"] == []

    with SessionLocal() as db:
        campaign = db.get(Campaign, campaign_id)
        shipment = db.query(Shipment).filter(Shipment.campaign_id == campaign_id).one()
        activities = db.query(Activity).filter(Activity.campaign_id == campaign_id).all()
        assert campaign.execution_status == "运输中"
        assert shipment.status == "运输中"
        assert shipment.oa_pi_number == "OA-TEST-100"
        assert shipment.tracking_number == "TRACK-TEST-200"
        assert any(item.activity_type == "状态更新" for item in activities)


def test_workflow_health_preserves_explicit_missing_fields_and_requests_next_step(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    headers = seeded_collaboration["headers"]

    missing = client.patch(
        f"/api/collaborations/{campaign_id}",
        headers=headers,
        json={"execution_status": "运输中", "next_action": None, "follow_up_date": None},
    )
    assert missing.status_code == 200
    assert missing.json()["next_action"] is None
    assert missing.json()["workflow_health"] == "missing_both"
    assert missing.json()["workflow_warnings"] == ["缺少下一步行动", "缺少跟进日期"]

    completed = client.patch(
        f"/api/collaborations/{campaign_id}",
        headers=headers,
        json={
            "next_action": "确认下一轮内容排期",
            "follow_up_date": "2026-08-20",
            "follow_up_done": True,
        },
    )
    assert completed.status_code == 200
    assert completed.json()["workflow_health"] == "needs_next_step"

    workbench = client.get("/api/workbench?queue=all", headers=headers)
    assert workbench.status_code == 200
    assert workbench.json()["items"][0]["workflow_label"] == "待续排"

    campaigns = client.get("/api/campaigns?page_size=20", headers=headers)
    assert campaigns.status_code == 200
    listed = campaigns.json()["items"][0]
    assert listed["media"]["name"] == "Test Creator"
    assert listed["project"]["name"] == "Test Launch"
    assert listed["workflow_health"] == "needs_next_step"


def test_archived_collaboration_disappears_and_can_be_restored(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    headers = seeded_collaboration["headers"]

    before = client.get("/api/workbench?queue=all", headers=headers)
    assert before.status_code == 200
    assert [item["id"] for item in before.json()["items"]] == [campaign_id]

    archived = client.post(f"/api/campaigns/{campaign_id}/archive", headers=headers)
    assert archived.status_code == 200

    hidden = client.get("/api/workbench?queue=all", headers=headers)
    assert hidden.status_code == 200
    assert hidden.json()["items"] == []

    restored = client.post(f"/api/campaigns/{campaign_id}/restore", headers=headers)
    assert restored.status_code == 200

    visible_again = client.get("/api/workbench?queue=all", headers=headers)
    assert visible_again.status_code == 200
    assert [item["id"] for item in visible_again.json()["items"]] == [campaign_id]

    with SessionLocal() as db:
        campaign = db.get(Campaign, campaign_id)
        assert campaign.is_historical is False
        assert campaign.archived_at is None
