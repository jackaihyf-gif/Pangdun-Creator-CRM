from backend.app.database import SessionLocal
from backend.app.models import Activity, Campaign, CampaignStageEvent, Shipment


def test_project_collaboration_tag_is_normalized_and_saved(client, seeded_collaboration):
    response = client.put(
        f"/api/projects/{seeded_collaboration['project_id']}",
        headers=seeded_collaboration["headers"],
        json={"name": "Test Launch", "status": "Active", "collaboration_tag": "launch2026"},
    )
    assert response.status_code == 200
    assert response.json()["collaboration_tag"] == "#launch2026"


def test_collaboration_patch_saves_follow_up_and_shipment(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    headers = seeded_collaboration["headers"]
    assert client.post(f"/api/collaborations/{campaign_id}/advance", headers=headers, json={"target_status": "待发货"}).status_code == 200
    advanced = client.post(f"/api/collaborations/{campaign_id}/advance", headers=headers, json={"target_status": "运输中", "tracking_number": "TRACK-TEST-200"})
    assert advanced.status_code == 200
    response = client.patch(
        f"/api/collaborations/{campaign_id}",
        headers=headers,
        json={
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
        assert any(item.activity_type == "阶段推进" for item in activities)


def test_workflow_health_preserves_explicit_missing_fields_and_requests_next_step(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    headers = seeded_collaboration["headers"]
    assert client.post(f"/api/collaborations/{campaign_id}/advance", headers=headers, json={"target_status": "待发货"}).status_code == 200
    assert client.post(f"/api/collaborations/{campaign_id}/advance", headers=headers, json={"target_status": "运输中", "tracking_number": "TRACK-MISSING-1"}).status_code == 200

    missing = client.patch(
        f"/api/collaborations/{campaign_id}",
        headers=headers,
        json={"next_action": None, "follow_up_date": None},
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


def test_safe_advance_requires_adjacent_stage_and_domain_evidence(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    headers = seeded_collaboration["headers"]

    preview = client.get(f"/api/collaborations/{campaign_id}", headers=headers).json()
    assert preview["next_status"] == "待发货"
    assert preview["advance_ready"] is True

    skipped = client.post(
        f"/api/collaborations/{campaign_id}/advance",
        headers=headers,
        json={"target_status": "运输中"},
    )
    assert skipped.status_code == 409

    pending_shipping = client.post(
        f"/api/collaborations/{campaign_id}/advance",
        headers=headers,
        json={"target_status": "待发货"},
    )
    assert pending_shipping.status_code == 200
    assert pending_shipping.json()["advance_blockers"] == ["缺少物流单号"]

    missing_tracking = client.post(
        f"/api/collaborations/{campaign_id}/advance",
        headers=headers,
        json={"target_status": "运输中"},
    )
    assert missing_tracking.status_code == 409
    assert missing_tracking.json()["detail"]["requirements"] == ["tracking_number"]

    in_transit = client.post(
        f"/api/collaborations/{campaign_id}/advance",
        headers=headers,
        json={"target_status": "运输中", "tracking_number": "SAFE-TRACK-1", "carrier": "DHL"},
    )
    assert in_transit.status_code == 200
    assert in_transit.json()["execution_status"] == "运输中"
    assert in_transit.json()["advance_requirements"] == ["delivered_at"]


def test_safe_advance_can_capture_content_publish_and_no_payment_confirmation(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    headers = seeded_collaboration["headers"]
    steps = [
        {"target_status": "待发货"},
        {"target_status": "运输中", "tracking_number": "SAFE-TRACK-2"},
        {"target_status": "已签收待产出", "delivered_at": "2026-08-12"},
        {"target_status": "内容审核中", "content_title": "首版评测视频"},
        {"target_status": "已发布", "publication_url": "https://example.test/published", "published_at": "2026-08-13"},
        {"target_status": "已结算", "no_payment_required": True},
    ]
    for body in steps:
        response = client.post(f"/api/collaborations/{campaign_id}/advance", headers=headers, json=body)
        assert response.status_code == 200, response.text

    completed = response.json()
    assert completed["execution_status"] == "已结算"
    assert completed["next_status"] is None
    assert completed["deliverables"][0]["url"] == "https://example.test/published"
    assert completed["cost_items"][0]["payment_status"] == "无需付款"
    assert any(row["activity_type"] == "阶段推进" for row in completed["activities"])


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


def test_status_changes_require_guarded_actions_and_are_recorded(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    headers = seeded_collaboration["headers"]
    rejected = client.patch(f"/api/collaborations/{campaign_id}", headers=headers, json={"execution_status": "已发布"})
    assert rejected.status_code == 409

    paused = client.post(f"/api/collaborations/{campaign_id}/status-action", headers=headers, json={"action": "pause", "reason": "等待客户确认预算"})
    assert paused.status_code == 200
    assert paused.json()["execution_status"] == "已暂停"
    resumed = client.post(f"/api/collaborations/{campaign_id}/status-action", headers=headers, json={"action": "resume"})
    assert resumed.status_code == 200
    assert resumed.json()["execution_status"] == "待确认"

    assert client.post(f"/api/collaborations/{campaign_id}/advance", headers=headers, json={"target_status": "待发货"}).status_code == 200
    rolled_back = client.post(f"/api/collaborations/{campaign_id}/status-action", headers=headers, json={"action": "rollback", "reason": "收件地址需要重新确认"})
    assert rolled_back.status_code == 200
    assert rolled_back.json()["execution_status"] == "待确认"
    with SessionLocal() as db:
        events = db.query(CampaignStageEvent).filter(CampaignStageEvent.campaign_id == campaign_id).all()
        assert [event.action for event in events][-4:] == ["pause", "resume", "advance", "rollback"]


def test_cancel_requires_reason_and_advance_can_be_undone(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    headers = seeded_collaboration["headers"]
    no_reason = client.post(f"/api/collaborations/{campaign_id}/status-action", headers=headers, json={"action": "cancel"})
    assert no_reason.status_code == 400

    advanced = client.post(f"/api/collaborations/{campaign_id}/advance", headers=headers, json={"target_status": "待发货"})
    assert advanced.status_code == 200
    undone = client.post(f"/api/collaborations/{campaign_id}/undo-advance", headers=headers)
    assert undone.status_code == 200
    assert undone.json()["execution_status"] == "待确认"

    cancelled = client.post(f"/api/collaborations/{campaign_id}/status-action", headers=headers, json={"action": "cancel", "reason": "达人明确拒绝本次合作"})
    assert cancelled.status_code == 200
    assert cancelled.json()["execution_status"] == "已取消"


def test_bulk_update_requires_preview_before_write(client, seeded_collaboration):
    campaign_id = seeded_collaboration["campaign_id"]
    headers = seeded_collaboration["headers"]
    preview = client.patch("/api/collaborations/bulk", headers=headers, json={"ids": [campaign_id], "follow_up_priority": "高"})
    assert preview.status_code == 200
    assert preview.json()["preview"] is True
    with SessionLocal() as db:
        assert db.get(Campaign, campaign_id).follow_up_priority != "高"
    applied = client.patch("/api/collaborations/bulk", headers=headers, json={"ids": [campaign_id], "follow_up_priority": "高", "preview": False})
    assert applied.status_code == 200
    assert applied.json()["updated"] == 1
    with SessionLocal() as db:
        assert db.get(Campaign, campaign_id).follow_up_priority == "高"
