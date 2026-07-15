from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import openpyxl
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import Campaign, Contact, Deliverable, Media


HEADERS = {
    "类目": "category",
    "国家": "country",
    "母公司": "parent_company",
    "名字": "name",
    "流量/粉丝": "followers_or_traffic",
    "网站类型": "platform_type",
    "链接": "website_url",
    "报价": "quotation",
    "合作情况": "cooperation",
    "合作链接": "deliverable_url",
    "联系人&职位": "contact_role",
    "联系方式": "contact_info",
    "合作备注": "notes",
    "合作备注2": "notes2",
    "是否发产品Brief": "brief_sent",
    "产品Brief 邮箱": "brief_email",
    "Press release邮箱": "press_release_email",
}
STAGE_MAP = {
    "待开发": "To Contact",
    "已联系": "Contacted",
    "等回复": "Waiting Reply",
    "报价": "Quoting",
    "要钱": "Quoting",
    "已发brief": "Brief Sent",
    "寄样": "Sample Sent",
    "制作": "In Production",
    "已产出": "Published",
    "拉黑": "Blacklisted",
    "暂停": "Paused",
}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")


@dataclass
class ImportResult:
    success_count: int
    skipped_count: int
    error_count: int
    errors: list[dict[str, Any]]
    rows: list[dict[str, Any]]


def load_rows(content: bytes) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    raw_rows = ws.iter_rows(values_only=True)
    headers = next(raw_rows, [])
    keys = [HEADERS.get(str(cell).strip(), None) if cell else None for cell in headers]
    rows: list[dict[str, Any]] = []
    for row_number, values in enumerate(raw_rows, start=2):
        item: dict[str, Any] = {"row_number": row_number}
        for key, value in zip(keys, values):
            if key and value not in (None, ""):
                item[key] = str(value).strip() if not isinstance(value, (int, float)) else value
        if any(k for k in item.keys() if k != "row_number"):
            rows.append(normalize_row(item))
    return rows


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    contact_name, contact_role = split_contact_role(str(row.get("contact_role", "")).strip())
    contact_info = str(row.get("contact_info", "")).strip()
    emails = EMAIL_RE.findall(contact_info)
    phones = PHONE_RE.findall(contact_info)
    cooperation = str(row.get("cooperation", "")).strip()
    stage = infer_stage(cooperation)
    notes_parts = [row.get("notes"), row.get("notes2")]
    if cooperation and not stage:
        notes_parts.append(f"合作情况: {cooperation}")
    quotation = row.get("quotation")
    amount, currency, quote_note = parse_quotation(quotation)
    if quote_note:
        notes_parts.append(f"报价: {quote_note}")
    return {
        **row,
        "contact_name": contact_name,
        "contact_role_text": contact_role,
        "email": emails[0] if emails else None,
        "phone": phones[0].strip() if phones else None,
        "telegram": "Telegram" if "telegram" in contact_info.lower() else None,
        "contact_notes": contact_info if not emails and not phones else contact_info,
        "stage": stage or "Not Started",
        "quotation_amount": amount,
        "quotation_currency": currency,
        "campaign_notes": "\n".join(str(x) for x in notes_parts if x),
        "brief_sent_bool": str(row.get("brief_sent", "")).strip() == "是",
    }


def split_contact_role(value: str) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    parts = value.split()
    if len(parts) <= 1:
        return value, None
    return " ".join(parts[:-1]), parts[-1]


def infer_stage(value: str) -> str | None:
    lowered = value.replace(" ", "").lower()
    for key, stage in STAGE_MAP.items():
        if key.lower() in lowered:
            return stage
    return None


def parse_quotation(value: Any) -> tuple[float | None, str | None, str | None]:
    if value in (None, ""):
        return None, None, None
    text = str(value).strip()
    if "免费" in text:
        return 0, "CNY", None
    match = re.search(r"(?P<currency>[$€£¥]|usd|eur|cny|rmb)?\s*(?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)", text, re.I)
    if not match:
        return None, None, text
    currency = match.group("currency") or None
    currency = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "CNY"}.get(currency, currency)
    return float(match.group("amount").replace(",", "")), currency.upper() if currency else None, None


def preview_import(content: bytes) -> ImportResult:
    rows = load_rows(content)
    return ImportResult(len(rows), 0, 0, [], rows[:100])


def confirm_import(db: Session, content: bytes) -> ImportResult:
    rows = load_rows(content)
    success = skipped = errors = 0
    error_rows: list[dict[str, Any]] = []
    preview_rows: list[dict[str, Any]] = []
    for row in rows:
        try:
            name = str(row.get("name", "")).strip()
            if not name:
                skipped += 1
                continue
            media = find_media(db, name, row.get("website_url"), row.get("country"))
            if not media:
                media = Media(
                    name=name,
                    country=row.get("country"),
                    category=row.get("category"),
                    platform_type=row.get("platform_type"),
                    website_url=row.get("website_url"),
                    followers_or_traffic=safe_int(row.get("followers_or_traffic")),
                    cooperation_status=row.get("cooperation"),
                    notes=row.get("parent_company"),
                )
                db.add(media)
                db.flush()
            contact = Contact(
                media_id=media.id,
                name=row.get("contact_name"),
                role=row.get("contact_role_text"),
                email=row.get("email"),
                phone=row.get("phone"),
                telegram=row.get("telegram"),
                brief_email=row.get("brief_email"),
                press_release_email=row.get("press_release_email"),
                notes=row.get("contact_notes"),
            )
            if contact.name or contact.email or contact.phone or contact.notes:
                db.add(contact)
            campaign = None
            if row.get("campaign_notes") or row.get("quotation_amount") is not None or row.get("brief_sent_bool"):
                campaign = Campaign(
                    media_id=media.id,
                    stage=row.get("stage", "Not Started"),
                    quotation_amount=row.get("quotation_amount"),
                    quotation_currency=row.get("quotation_currency"),
                    brief_sent=row.get("brief_sent_bool", False),
                    notes=row.get("campaign_notes"),
                )
                db.add(campaign)
                db.flush()
            if campaign and row.get("deliverable_url"):
                db.add(Deliverable(campaign_id=campaign.id, url=row.get("deliverable_url"), deliverable_type="Other"))
            success += 1
            if len(preview_rows) < 100:
                preview_rows.append(row)
        except Exception as exc:
            db.rollback()
            errors += 1
            error_rows.append({"row_number": row.get("row_number"), "error": str(exc)})
        else:
            db.commit()
    return ImportResult(success, skipped, errors, error_rows, preview_rows)


def find_media(db: Session, name: str, website_url: str | None, country: str | None) -> Media | None:
    if website_url:
        return db.query(Media).filter(Media.name == name, Media.website_url == website_url).first()
    return db.query(Media).filter(Media.name == name, or_(Media.country == country, Media.country.is_(None))).first()


def safe_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
