"""Remove legacy default-only records from the media review queue."""

from __future__ import annotations

import argparse
import json
import re

from backend.app.database import SessionLocal
from backend.app.models import AuditLog, Media, User


def has_actionable_issue(item: Media) -> bool:
    has_contact_method = any(
        any((contact.email, contact.phone, contact.whatsapp, contact.telegram, contact.brief_email, contact.press_release_email))
        for contact in item.contacts
    )
    has_data_flag = bool(re.search(r"\[数据核验\]\s*([^\n]+)", item.notes or ""))
    return not has_contact_method or has_data_flag or item.verification_status == "有冲突"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        pending = db.query(Media).filter(Media.verification_status != "已核验").all()
        resolved = [item for item in pending if not has_actionable_issue(item)]
        plan = {"before": len(pending), "auto_verified": len(resolved), "remaining": len(pending) - len(resolved), "media_ids": [item.id for item in resolved]}
        if not args.apply:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            print("Dry-run only; add --apply to write changes.")
            return
        for item in resolved:
            item.verification_status = "已核验"
        user = db.query(User).filter(User.role == "Admin").first()
        db.add(AuditLog(
            user_id=user.id if user else None,
            action="fix_media_review_queue",
            entity_type="media",
            entity_id="default-status-cleanup",
            before_json=json.dumps({"queue_total": len(pending)}, ensure_ascii=False),
            after_json=json.dumps(plan, ensure_ascii=False),
            reason="移除仅因历史默认待核验状态进入队列、但没有明确数据问题的媒体",
        ))
        db.commit()
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
