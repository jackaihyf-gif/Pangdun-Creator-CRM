from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import openpyxl
from sqlalchemy.orm import Session

from .models import Campaign, CostItem, Deliverable, Media, Project, Shipment, ShipmentItem
from .product_backfill import ensure_project_link, find_or_create_product


STATUS_MAP = {
    "已产出": "已发布",
    "已到货待产出": "已签收待产出",
    "已发货待收": "运输中",
    "代理发货": "运输中",
    "待发货": "待发货",
}


def value(row: dict[str, Any], key: str) -> str | None:
    item = row.get(key)
    return str(item).strip() if item not in (None, "") else None


def number(row: dict[str, Any], key: str) -> float | None:
    item = row.get(key)
    if item in (None, ""):
        return None
    try:
        return float(item)
    except (TypeError, ValueError):
        return None


def load_execution_rows(content: bytes) -> list[dict[str, Any]]:
    workbook = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    sheet = workbook[workbook.sheetnames[0]]
    values = sheet.iter_rows(values_only=True)
    headers = [str(cell).strip() if cell else "" for cell in next(values, [])]
    rows = []
    for row_number, row in enumerate(values, start=2):
        item = dict(zip(headers, row))
        if any(cell not in (None, "") for cell in row):
            item["_row_number"] = row_number
            rows.append(item)
    return rows


def preview_execution_import(content: bytes) -> dict[str, Any]:
    rows = load_execution_rows(content)
    previews = []
    warning_count = 0
    for row in rows:
        code = value(row, "OA PI编号")
        channel = value(row, "Channel") or "未命名渠道"
        warnings = []
        if not code:
            warnings.append("缺少 OA/PI，将进入历史导入待归类项目")
        if not value(row, "频道链接"):
            warnings.append("缺少频道链接，媒体去重需人工确认")
        warning_count += len(warnings)
        previews.append({
            "row_number": row["_row_number"],
            "project_code": code,
            "media_name": channel,
            "country": value(row, "国家"),
            "channel": value(row, "渠道"),
            "execution_status": STATUS_MAP.get(value(row, "进度") or "", "待确认"),
            "product_bundle": value(row, "产品类型"),
            "tracking_number": value(row, "追踪编号"),
            "content_url": value(row, "产出内容链接"),
            "warnings": warnings,
        })
    return {"total": len(rows), "warning_count": warning_count, "rows": previews}


def find_or_create_media(db: Session, row: dict[str, Any]) -> Media:
    name = value(row, "Channel") or "未命名渠道"
    url = value(row, "频道链接")
    query = db.query(Media).filter(Media.name == name)
    if url:
        item = query.filter(Media.website_url == url).first()
    else:
        item = query.filter(Media.country == value(row, "国家")).first()
    if item:
        return item
    item = Media(name=name, country=value(row, "国家"), platform_type=value(row, "渠道"), website_url=url)
    db.add(item)
    db.flush()
    return item


def confirm_execution_import(db: Session, content: bytes) -> dict[str, Any]:
    rows = load_execution_rows(content)
    fallback = db.query(Project).filter(Project.project_code == "HISTORY-UNSORTED").first()
    if not fallback:
        fallback = Project(name="历史导入待归类", project_code="HISTORY-UNSORTED", status="Active", notes="来自费用统计表、缺少 OA/PI 编号的历史记录")
        db.add(fallback)
        db.flush()
    imported = 0
    projects: dict[str, Project] = {}
    for row in rows:
        code = value(row, "OA PI编号")
        project = fallback
        if code:
            project = projects.get(code) or db.query(Project).filter(Project.project_code == code).first()
            if not project:
                project = Project(name=f"历史导入 {code}", project_code=code, status="Active")
                db.add(project)
                db.flush()
            projects[code] = project
        media = find_or_create_media(db, row)
        campaign = Campaign(
            project_id=project.id,
            media_id=media.id,
            collaboration_type=value(row, "推广形式"),
            execution_status=STATUS_MAP.get(value(row, "进度") or "", "待确认"),
            stage="Published" if value(row, "进度") == "已产出" else "Not Started",
            notes="\n".join(part for part in [value(row, "合作备注"), value(row, "合作备注2（当前情况）")] if part),
        )
        db.add(campaign)
        db.flush()
        shipment = Shipment(
            campaign_id=campaign.id,
            recipient_address=value(row, "地址信息"),
            oa_pi_number=code,
            tracking_number=value(row, "追踪编号"),
            status=STATUS_MAP.get(value(row, "进度") or "", "待确认"),
        )
        db.add(shipment)
        db.flush()
        product_bundle = value(row, "产品类型")
        if product_bundle:
            for product_name in product_bundle.split("\n"):
                if product_name.strip():
                    product = find_or_create_product(db, product_name.strip(), "费用表导入")
                    ensure_project_link(db, project.id, product.id)
                    db.add(ShipmentItem(shipment_id=shipment.id, product_id=product.id, product_name=product.model))
        for label, source in [("产品费用", "产品费用"), ("物流/关税", "运费/保费/关税预付"), ("评测费用", "评测费用")]:
            amount = number(row, source)
            if amount is not None:
                db.add(CostItem(campaign_id=campaign.id, cost_type=label, actual_amount=amount, currency="CNY", payment_status="已付款"))
        content_url = value(row, "产出内容链接")
        if content_url:
            db.add(Deliverable(campaign_id=campaign.id, deliverable_type=value(row, "渠道") or "Other", url=content_url, views=None))
        imported += 1
    db.commit()
    return {"success_count": imported, "project_count": len(projects) + 1, "fallback_count": sum(1 for row in rows if not value(row, "OA PI编号"))}
