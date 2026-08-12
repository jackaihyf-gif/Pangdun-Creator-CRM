"""One-off deterministic cleanup for the 2026-08 media audit.

The script intentionally limits destructive work to exact duplicates and
manually reviewed media aliases. Run without --apply for a plan.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from backend.app.database import SessionLocal
from backend.app.models import (
    Activity,
    AuditLog,
    Campaign,
    Contact,
    CostItem,
    Deliverable,
    Media,
    Shipment,
    ShippingAddress,
    User,
)


MEDIA_MERGES = {
    3: 85,     # Мой Компьютер / @mka (same published channel URL)
    151: 6,    # ARX Media
    162: 37,   # Beacons
    160: 65,   # Wccftech
    169: 68,   # Laurent's Choice
    150: 69,   # Linus Tech Tips
    166: 69,
    159: 83,   # iXBT
    164: 142,  # Alex / AZisk
    165: 148,  # PCMaster
    157: 37,   # nedalex Beacons media kit
    156: 54,   # Tom's Hardware
    153: 145,  # Mohamed Mamouni / Mimho
    158: 146,  # Gambino Gaming
}

ENRICHMENTS = {
    15: {"platform_type": "科技媒体 / 网站", "website_url": "https://www.xfastest.com/", "profile_links": [{"platform": "网站", "url": "https://www.xfastest.com/"}]},
    42: {"platform_type": "YouTube", "website_url": "https://www.youtube.com/@techyescity", "profile_links": [{"platform": "YouTube", "url": "https://www.youtube.com/@techyescity"}], "followers_or_traffic": 625.0, "audience_metric_type": "粉丝量", "audience_metric_unit": "K"},
    43: {"platform_type": "YouTube", "website_url": "https://www.youtube.com/@Hardwareunboxed", "profile_links": [{"platform": "YouTube", "url": "https://www.youtube.com/@Hardwareunboxed"}], "followers_or_traffic": 1170.0, "audience_metric_type": "粉丝量", "audience_metric_unit": "K"},
    63: {"name": "Provoke Media", "website_url": "https://www.provokemedia.com/", "profile_links": [{"platform": "网站", "url": "https://www.provokemedia.com/"}]},
    72: {"platform_type": "其他", "website_url": "https://pinkxxiny.passio.eco/", "profile_links": [{"platform": "网站", "url": "https://pinkxxiny.passio.eco/"}]},
    73: {"country": "英国"},
    76: {"name": "EnosTech", "platform_type": "科技媒体 / 网站", "website_url": "https://www.enostech.com/", "profile_links": [{"platform": "网站", "url": "https://www.enostech.com/"}]},
    77: {"country": "西班牙"},
    78: {"country": "西班牙", "website_url": "https://elchapuzasinformatico.com/", "profile_links": [{"platform": "网站", "url": "https://elchapuzasinformatico.com/"}]},
    79: {"country": "西班牙"},
    80: {"country": "西班牙", "platform_type": "YouTube", "website_url": "https://www.youtube.com/@rincondelvaro", "profile_links": [{"platform": "YouTube", "url": "https://www.youtube.com/@rincondelvaro"}], "followers_or_traffic": 498.0, "audience_metric_type": "粉丝量", "audience_metric_unit": "K"},
    83: {"name": "iXBT.com", "platform_type": "科技媒体 / 网站", "website_url": "https://www.ixbt.com/", "profile_links": [{"platform": "网站", "url": "https://www.ixbt.com/"}], "audience_metric_type": "月访问量", "audience_metric_unit": "K"},
    117: {"name": "Quasarzone", "platform_type": "科技媒体 / 网站", "website_url": "https://quasarzone.com/", "profile_links": [{"platform": "网站", "url": "https://quasarzone.com/"}], "audience_metric_type": "月访问量", "audience_metric_unit": "K"},
    122: {"name": "Overclocking.com", "platform_type": "科技媒体 / 网站", "website_url": "https://overclocking.com/", "profile_links": [{"platform": "网站", "url": "https://overclocking.com/"}], "audience_metric_type": "月访问量", "audience_metric_unit": "K"},
    69: {"country": "加拿大", "platform_type": "YouTube", "website_url": "https://www.youtube.com/@LinusTechTips", "profile_links": [{"platform": "YouTube", "url": "https://www.youtube.com/@LinusTechTips"}]},
    85: {"name": "Мой Компьютер / @mka"},
}

REVIEW_FLAGS = {
    161: "[数据核验] 历史执行单仍有关联，但缺少真实媒体名称、主页和联系人；请根据项目 202601231022000170383 补录。",
    163: "[数据核验] 历史执行单仍有关联，名称仅为平台 Instagram，缺少账号主页和联系人；请人工补录。",
    167: "[数据核验] 历史执行单仍有关联，但未找到可唯一确认的 RafeyTech 官方主页；请人工确认账号。",
}


def campaign_signature(item: Campaign) -> tuple:
    return (
        item.media_id, item.project_id, item.product_id, item.owner_id,
        item.collaboration_type, item.execution_status, item.stage,
        item.quotation_amount, item.quotation_currency, item.brief_sent,
        item.brief_sent_at, item.sample_status, item.expected_publish_date,
        item.actual_publish_date, item.notes, item.next_action,
        item.follow_up_date, item.follow_up_priority, item.follow_up_done,
        item.is_historical, item.archived_at,
    )


def child_signature(item, excluded: set[str]) -> tuple:
    return tuple(
        (column.name, getattr(item, column.name))
        for column in item.__table__.columns
        if column.name not in excluded
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plan = {
        "media_merges": MEDIA_MERGES,
        "enrich_media_ids": sorted(ENRICHMENTS),
        "review_media_ids": sorted(REVIEW_FLAGS),
    }
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        print("Dry-run only; add --apply to write changes.")
        return

    db = SessionLocal()
    summary = defaultdict(int)
    try:
        # Merge reviewed aliases while retaining all linked business history.
        for source_id, target_id in MEDIA_MERGES.items():
            source, target = db.get(Media, source_id), db.get(Media, target_id)
            if not source or not target:
                continue
            for contact in list(source.contacts):
                contact.media = target
            for address in list(source.shipping_addresses):
                address.media = target
            for campaign in list(source.campaigns):
                campaign.media = target
            if not target.website_url and source.website_url:
                target.website_url = source.website_url
                target.profile_links = source.profile_links or []
            db.flush()
            db.delete(source)
            summary["media_merged"] += 1
        db.flush()

        for media_id, values in ENRICHMENTS.items():
            item = db.get(Media, media_id)
            if not item:
                continue
            for key, value in values.items():
                setattr(item, key, value)
            summary["media_enriched"] += 1

        for media_id, marker in REVIEW_FLAGS.items():
            item = db.get(Media, media_id)
            if not item:
                continue
            item.cooperation_status = "待核验"
            if marker not in (item.notes or ""):
                item.notes = "\n".join(part for part in [item.notes, marker] if part)
            summary["media_flagged"] += 1

        # Normalize a contact whose email was imported into the name field.
        email_contact = db.get(Contact, 15)
        if email_contact and not email_contact.email and "@" in (email_contact.name or ""):
            email_contact.email = email_contact.name.strip()
            email_contact.name = None
            summary["contacts_repaired"] += 1
        db.flush()

        # Remove exact duplicate campaigns. Move any unique children to the
        # earliest campaign and discard only exact duplicate children.
        groups: dict[tuple, list[Campaign]] = defaultdict(list)
        for item in db.query(Campaign).order_by(Campaign.id).all():
            groups[campaign_signature(item)].append(item)
        child_models = [Shipment, CostItem, Deliverable, Activity]
        for group in groups.values():
            if len(group) < 2:
                continue
            target = group[0]
            for source in group[1:]:
                for model in child_models:
                    existing = {
                        child_signature(row, {"id", "campaign_id", "created_at", "data_updated_at"})
                        for row in db.query(model).filter(model.campaign_id == target.id).all()
                    }
                    for row in db.query(model).filter(model.campaign_id == source.id).all():
                        signature = child_signature(row, {"id", "campaign_id", "created_at", "data_updated_at"})
                        if signature in existing:
                            db.delete(row)
                            summary["duplicate_child_rows_removed"] += 1
                        else:
                            row.campaign_id = target.id
                            existing.add(signature)
                            summary["child_rows_moved"] += 1
                db.flush()
                db.delete(source)
                summary["duplicate_campaigns_removed"] += 1
        db.flush()

        # Remove exact duplicate contacts created by repeated imports.
        contact_groups: dict[tuple, list[Contact]] = defaultdict(list)
        for item in db.query(Contact).order_by(Contact.id).all():
            contact_groups[child_signature(item, {"id"})].append(item)
        for group in contact_groups.values():
            for duplicate in group[1:]:
                db.delete(duplicate)
                summary["duplicate_contacts_removed"] += 1

        user = db.query(User).filter(User.role == "Admin").first()
        db.add(AuditLog(
            user_id=user.id if user else None,
            action="deep_clean",
            entity_type="crm_data",
            entity_id="batch",
            before_json=None,
            after_json=json.dumps(dict(summary), ensure_ascii=False),
            reason="合并影子媒体、去除重复导入记录、补齐可确认主页并标记待核验数据",
        ))
        db.commit()
        print(json.dumps(dict(summary), ensure_ascii=False, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
