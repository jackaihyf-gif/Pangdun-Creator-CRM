from __future__ import annotations

import re

from sqlalchemy.orm import Session

from .models import Campaign, Product, ProjectProduct, Shipment, ShipmentItem


CHIPSET_RE = re.compile(r"\b([BXZ]\d{3,4}[A-Z]?)\b", re.I)


def product_model(value: str) -> str:
    return value.strip()


def chipset_from_model(value: str) -> str | None:
    match = CHIPSET_RE.search(value)
    return match.group(1).upper() if match else None


def ensure_project_link(db: Session, project_id: int | None, product_id: int) -> None:
    if project_id is None:
        return
    exists = db.query(ProjectProduct).filter(ProjectProduct.project_id == project_id, ProjectProduct.product_id == product_id).first()
    if not exists:
        db.add(ProjectProduct(project_id=project_id, product_id=product_id))
        db.flush()


def find_or_create_product(db: Session, raw_name: str, source_note: str | None = None) -> Product:
    model = product_model(raw_name)
    item = db.query(Product).filter(Product.model == model).first()
    if item:
        return item
    item = Product(
        model=model,
        full_name=model,
        platform=chipset_from_model(model),
        notes=source_note or "来自寄样产品明细",
    )
    db.add(item)
    db.flush()
    return item


def backfill_products(db: Session) -> dict[str, int]:
    created = linked_items = linked_projects = 0
    items = db.query(ShipmentItem).join(Shipment).join(Campaign).all()
    for item in items:
        if not item.product_name:
            continue
        before = db.query(Product).filter(Product.model == product_model(item.product_name)).first()
        product = find_or_create_product(db, item.product_name, "历史寄样明细回填")
        if before is None:
            created += 1
        if item.product_id != product.id:
            item.product_id = product.id
            linked_items += 1
        campaign = item.shipment.campaign
        exists = db.query(ProjectProduct).filter(ProjectProduct.project_id == campaign.project_id, ProjectProduct.product_id == product.id).first() if campaign.project_id else True
        ensure_project_link(db, campaign.project_id, product.id)
        if not exists:
            linked_projects += 1
    db.commit()
    return {"created": created, "linked_items": linked_items, "linked_projects": linked_projects}
