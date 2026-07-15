from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from .auth import clear_session_cookie, current_user, hash_password, require_roles, set_session_cookie, verify_password
from .database import Base, apply_compat_migrations, engine, get_db
from .execution_importer import confirm_execution_import, preview_execution_import
from .importer import confirm_import, preview_import
from .models import Activity, Campaign, Contact, CostItem, Deliverable, Media, Product, Project, ProjectProduct, Shipment, ShipmentItem, ShippingAddress, User
from .product_backfill import backfill_products, ensure_project_link, find_or_create_product
from .schemas import (
    CampaignBase,
    CampaignOut,
    ContactBase,
    ContactOut,
    DeliverableBase,
    DeliverableOut,
    LoginIn,
    MediaBase,
    MediaOut,
    ProductBase,
    ProductMergeIn,
    ProductOut,
    ProjectBase,
    ProjectOut,
    ShipmentBase,
    ShipmentOut,
    ShippingAddressBase,
    ShippingAddressOut,
    CostItemBase,
    CostItemOut,
    ActivityBase,
    ActivityOut,
    CollaborationBulkPatch,
    CollaborationPatch,
    ProjectShipmentBase,
    UserCreate,
    UserOut,
    UserUpdate,
)


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "frontend" / "dist"
STAGES = {
    "Not Started",
    "To Contact",
    "Contacted",
    "Waiting Reply",
    "Quoting",
    "Brief Sent",
    "Sample Sent",
    "In Production",
    "Published",
    "Closed",
    "Paused",
    "Blacklisted",
}
SAMPLE_STATUSES = {
    "Not Needed",
    "Not Sent",
    "Preparing",
    "Shipped",
    "In Transit",
    "Customs Clearance",
    "Delivered",
    "Issue",
}
DELIVERABLE_TYPES = {
    "YouTube Video",
    "YouTube Shorts",
    "Website Article",
    "Instagram Reel",
    "TikTok Video",
    "Press Release",
    "Other",
}
EXECUTION_STATUSES = {"待确认", "待发货", "运输中", "已签收待产出", "内容审核中", "已发布", "已结算", "已暂停/取消"}

SHIPMENT_STATUS_PROGRESS = {
    "待发货": 1,
    "运输中": 2,
    "已签收待产出": 3,
}
HISTORICAL_PROJECT_PREFIX = "历史导入"

Base.metadata.create_all(bind=engine)
apply_compat_migrations()
with next(get_db()) as bootstrap_db:
    backfill_products(bootstrap_db)

app = FastAPI(title="Pangdun KOL CRM")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def list_payload(query, page: int, page_size: int):
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": jsonable_encoder(items), "total": total}


def editable_user(user: Annotated[User, Depends(require_roles("Admin", "Editor"))]) -> User:
    return user


def validate_campaign(payload: CampaignBase) -> None:
    if payload.stage not in STAGES:
        raise HTTPException(400, f"Invalid stage: {payload.stage}")
    if payload.sample_status not in SAMPLE_STATUSES:
        raise HTTPException(400, f"Invalid sample status: {payload.sample_status}")
    if payload.execution_status not in EXECUTION_STATUSES:
        raise HTTPException(400, f"Invalid execution status: {payload.execution_status}")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/auth/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, db: Annotated[Session, Depends(get_db)]):
    user = db.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    set_session_cookie(response, user)
    return user


@app.post("/api/auth/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me", response_model=UserOut)
def me(user: Annotated[User, Depends(current_user)]):
    return user


@app.get("/api/options")
def options(user: Annotated[User, Depends(current_user)]):
    return {
        "roles": ["Admin", "Editor", "Viewer"],
        "stages": sorted(STAGES),
        "sample_statuses": sorted(SAMPLE_STATUSES),
        "deliverable_types": sorted(DELIVERABLE_TYPES),
        "execution_statuses": sorted(EXECUTION_STATUSES),
        "payment_statuses": ["未付款", "部分付款", "已付款", "无需付款"],
    }


@app.get("/api/users", response_model=dict)
def list_users(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    items = db.query(User).order_by(User.created_at.desc()).all()
    return {"items": jsonable_encoder(items), "total": db.query(User).count()}


@app.post("/api/users", response_model=UserOut)
def create_user(payload: UserCreate, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    if db.query(User).filter(func.lower(User.email) == payload.email.lower()).first():
        raise HTTPException(400, "Email already exists")
    item = User(email=payload.email.lower(), name=payload.name, role=payload.role, password_hash=hash_password(payload.password))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/users/{item_id}", response_model=UserOut)
def update_user(item_id: int, payload: UserUpdate, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    item = db.get(User, item_id)
    if not item:
        raise HTTPException(404, "User not found")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data and data["password"]:
        item.password_hash = hash_password(data.pop("password"))
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/media", response_model=dict)
def list_media(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    q: str | None = None,
    country: str | None = None,
    platform_type: str | None = None,
    media_tier: str | None = None,
    cooperation_status: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    query = db.query(Media)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Media.name.ilike(like),
            Media.website_url.ilike(like),
            Media.notes.ilike(like),
            Media.contacts.any(or_(Contact.name.ilike(like), Contact.email.ilike(like), Contact.phone.ilike(like))),
        ))
    if country:
        query = query.filter(Media.country == country)
    if platform_type:
        query = query.filter(Media.platform_type == platform_type)
    if media_tier:
        query = query.filter(Media.media_tier == media_tier)
    if cooperation_status:
        query = query.filter(Media.cooperation_status == cooperation_status)
    return list_payload(query.order_by(Media.updated_at.desc()), page, page_size)


@app.get("/api/media-duplicates")
def media_duplicates(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    name: str,
    website_url: str | None = None,
    country: str | None = None,
):
    query = db.query(Media).filter(func.lower(Media.name) == name.strip().lower())
    if website_url:
        query = query.filter(Media.website_url == website_url.strip())
    elif country:
        query = query.filter(Media.country == country.strip())
    return {"items": jsonable_encoder(query.order_by(Media.updated_at.desc()).limit(10).all())}


@app.post("/api/media", response_model=MediaOut)
def create_media(payload: MediaBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = Media(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/media/{item_id}")
def media_detail(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    item = db.query(Media).options(joinedload(Media.contacts), joinedload(Media.shipping_addresses).joinedload(ShippingAddress.contact), joinedload(Media.campaigns).joinedload(Campaign.product)).filter(Media.id == item_id).first()
    if not item:
        raise HTTPException(404, "Media not found")
    deliverables = (
        db.query(Deliverable)
        .join(Campaign)
        .filter(Campaign.media_id == item_id)
        .order_by(Deliverable.published_at.desc().nullslast())
        .all()
    )
    return {
        "media": jsonable_encoder({
            "id": item.id,
            "name": item.name,
            "country": item.country,
            "region": item.region,
            "category": item.category,
            "platform_type": item.platform_type,
            "website_url": item.website_url,
            "followers_or_traffic": item.followers_or_traffic,
            "media_tier": item.media_tier,
            "cooperation_status": item.cooperation_status,
            "notes": item.notes,
        }),
        "contacts": [jsonable_encoder({
            "id": contact.id,
            "media_id": contact.media_id,
            "name": contact.name,
            "role": contact.role,
            "email": contact.email,
            "phone": contact.phone,
            "whatsapp": contact.whatsapp,
            "telegram": contact.telegram,
            "brief_email": contact.brief_email,
            "press_release_email": contact.press_release_email,
            "is_primary": contact.is_primary,
            "notes": contact.notes,
        }) for contact in item.contacts],
        "shipping_addresses": [ShippingAddressOut.model_validate(address).model_dump(mode="json") for address in sorted(item.shipping_addresses, key=lambda address: (not address.is_default, address.id))],
        "campaigns": [{"id": campaign.id, "project_id": campaign.project_id, "execution_status": campaign.execution_status, "updated_at": campaign.updated_at} for campaign in item.campaigns],
        "deliverables": [{"id": deliverable.id, "url": deliverable.url, "deliverable_type": deliverable.deliverable_type, "published_at": deliverable.published_at} for deliverable in deliverables],
    }


@app.put("/api/media/{item_id}", response_model=MediaOut)
def update_media(item_id: int, payload: MediaBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.get(Media, item_id)
    if not item:
        raise HTTPException(404, "Media not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/media/{item_id}")
def delete_media(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    item = db.get(Media, item_id)
    if not item:
        raise HTTPException(404, "Media not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


@app.get("/api/products", response_model=dict)
def list_products(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)], q: str | None = None, page: int = 1, page_size: int = 20):
    query = db.query(Product).options(joinedload(Product.project_links).joinedload(ProjectProduct.project))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.model.ilike(like), Product.full_name.ilike(like), Product.aliases.ilike(like)))
    total = query.count()
    items = query.order_by(Product.model).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [product_payload(db, item) for item in items], "total": total}


def product_payload(db: Session, item: Product) -> dict:
    payload = jsonable_encoder(item)
    payload["project_ids"] = [link.project_id for link in item.project_links]
    payload["projects"] = [{"id": link.project.id, "name": link.project.name, "project_code": link.project.project_code} for link in item.project_links if link.project]
    payload["shipment_count"] = db.query(func.count(ShipmentItem.id)).filter(ShipmentItem.product_id == item.id).scalar() or 0
    return payload


def sync_product_projects(db: Session, item: Product, project_ids: list[int]) -> None:
    valid_ids = {project.id for project in db.query(Project).filter(Project.id.in_(project_ids)).all()} if project_ids else set()
    if len(valid_ids) != len(set(project_ids)):
        raise HTTPException(400, "One or more projects do not exist")
    for link in list(item.project_links):
        if link.project_id not in valid_ids:
            db.delete(link)
    current_ids = {link.project_id for link in item.project_links}
    for project_id in valid_ids - current_ids:
        db.add(ProjectProduct(project_id=project_id, product_id=item.id))


@app.post("/api/products")
def create_product(payload: ProductBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    data = payload.model_dump()
    project_ids = data.pop("project_ids", [])
    if db.query(Product).filter(Product.model == data["model"].strip()).first():
        raise HTTPException(400, "Product model already exists")
    data["model"] = data["model"].strip()
    if not data.get("platform"):
        from .product_backfill import chipset_from_model
        data["platform"] = chipset_from_model(data["model"])
    item = Product(**data)
    db.add(item)
    db.flush()
    sync_product_projects(db, item, project_ids)
    db.commit()
    db.refresh(item)
    return product_payload(db, item)


@app.get("/api/products/{item_id}")
def product_detail(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    item = db.get(Product, item_id)
    if not item:
        raise HTTPException(404, "Product not found")
    campaigns = (
        db.query(Campaign)
        .options(joinedload(Campaign.media), joinedload(Campaign.owner), joinedload(Campaign.deliverables))
        .filter(Campaign.product_id == item_id)
        .order_by(Campaign.updated_at.desc())
        .all()
    )
    db.refresh(item)
    return {"product": product_payload(db, item), "campaigns": campaigns}


@app.put("/api/products/{item_id}")
def update_product(item_id: int, payload: ProductBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.get(Product, item_id)
    if not item:
        raise HTTPException(404, "Product not found")
    data = payload.model_dump()
    project_ids = data.pop("project_ids", [])
    for key, value in data.items():
        setattr(item, key, value)
    sync_product_projects(db, item, project_ids)
    db.commit()
    db.refresh(item)
    return product_payload(db, item)


@app.delete("/api/products/{item_id}")
def delete_product(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    item = db.get(Product, item_id)
    if not item:
        raise HTTPException(404, "Product not found")
    campaign_count = db.query(func.count(Campaign.id)).filter(Campaign.product_id == item_id).scalar() or 0
    shipment_count = db.query(func.count(ShipmentItem.id)).filter(ShipmentItem.product_id == item_id).scalar() or 0
    if campaign_count or shipment_count:
        raise HTTPException(400, "This product is still referenced. Merge it into another product before deleting.")
    db.delete(item)
    db.commit()
    return {"ok": True}


@app.post("/api/products/{item_id}/merge")
def merge_product(item_id: int, payload: ProductMergeIn, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    source = db.query(Product).options(joinedload(Product.project_links)).filter(Product.id == item_id).first()
    target = db.query(Product).options(joinedload(Product.project_links)).filter(Product.id == payload.target_product_id).first()
    if not source or not target:
        raise HTTPException(404, "Product not found")
    if source.id == target.id:
        raise HTTPException(400, "Choose a different target product")
    campaign_count = db.query(func.count(Campaign.id)).filter(Campaign.product_id == source.id).scalar() or 0
    shipment_count = db.query(func.count(ShipmentItem.id)).filter(ShipmentItem.product_id == source.id).scalar() or 0
    target_project_ids = {link.project_id for link in target.project_links}
    for link in source.project_links:
        if link.project_id not in target_project_ids:
            db.add(ProjectProduct(project_id=link.project_id, product_id=target.id))
    db.query(Campaign).filter(Campaign.product_id == source.id).update({Campaign.product_id: target.id}, synchronize_session=False)
    db.query(ShipmentItem).filter(ShipmentItem.product_id == source.id).update({ShipmentItem.product_id: target.id, ShipmentItem.product_name: target.model}, synchronize_session=False)
    db.delete(source)
    db.commit()
    return {"ok": True, "campaign_count": campaign_count, "shipment_count": shipment_count, "target_product_id": target.id}


@app.get("/api/projects", response_model=dict)
def list_projects(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)], q: str | None = None, status: str | None = None, history_only: bool = False, page: int = 1, page_size: int = 100):
    query = db.query(Project).options(joinedload(Project.owner))
    if history_only:
        query = query.filter(or_(Project.is_archived.is_(True), Project.name.like(f"{HISTORICAL_PROJECT_PREFIX}%")))
    else:
        query = query.filter(Project.is_archived.is_(False), ~Project.name.like(f"{HISTORICAL_PROJECT_PREFIX}%"))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Project.name.ilike(like), Project.project_code.ilike(like), Project.objective.ilike(like)))
    if status:
        query = query.filter(Project.status == status)
    items = query.order_by(Project.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    rows = []
    for item in items:
        actual = db.query(func.coalesce(func.sum(CostItem.actual_amount), 0)).join(Campaign).filter(Campaign.project_id == item.id).scalar() or 0
        rows.append({**jsonable_encoder(item), "owner": jsonable_encoder(item.owner) if item.owner else None, "actual_amount": actual, "campaign_count": len(item.campaigns)})
    return {"items": rows, "total": query.count()}


@app.post("/api/projects", response_model=ProjectOut)
def create_project(payload: ProjectBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    if payload.project_code and db.query(Project).filter(Project.project_code == payload.project_code).first():
        raise HTTPException(400, "Project code already exists")
    item = Project(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/projects/{item_id}")
def project_detail(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    item = db.query(Project).options(joinedload(Project.owner), joinedload(Project.product_links).joinedload(ProjectProduct.product), joinedload(Project.campaigns).joinedload(Campaign.media), joinedload(Project.campaigns).joinedload(Campaign.owner), joinedload(Project.campaigns).joinedload(Campaign.shipments).joinedload(Shipment.items), joinedload(Project.campaigns).joinedload(Campaign.deliverables), joinedload(Project.campaigns).joinedload(Campaign.cost_items), joinedload(Project.campaigns).joinedload(Campaign.activities)).filter(Project.id == item_id).first()
    if not item:
        raise HTTPException(404, "Project not found")
    planned = sum(cost.planned_amount or 0 for campaign in item.campaigns for cost in campaign.cost_items)
    actual = sum(cost.actual_amount or 0 for campaign in item.campaigns for cost in campaign.cost_items)
    return jsonable_encoder({
        "project": project_detail_payload(item),
        "planned_amount": planned,
        "actual_amount": actual,
        "summary": project_result_summary(item),
        "campaigns": [campaign_detail_payload(campaign) for campaign in item.campaigns],
        "products": [product_detail_payload(link.product) for link in item.product_links if link.product],
    })


def user_summary_payload(item: User | None) -> dict | None:
    if not item:
        return None
    return {"id": item.id, "name": item.name, "email": item.email, "role": item.role}


def media_summary_payload(item: Media | None) -> dict | None:
    if not item:
        return None
    return {"id": item.id, "name": item.name, "country": item.country, "platform_type": item.platform_type, "website_url": item.website_url}


def product_detail_payload(item: Product) -> dict:
    return {
        "id": item.id,
        "model": item.model,
        "full_name": item.full_name,
        "product_line": item.product_line,
        "platform": item.platform,
        "aliases": item.aliases,
        "launch_status": item.launch_status,
        "notes": item.notes,
    }


def project_detail_payload(item: Project) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "project_code": item.project_code,
        "owner_id": item.owner_id,
        "owner": user_summary_payload(item.owner),
        "objective": item.objective,
        "status": item.status,
        "start_date": item.start_date,
        "end_date": item.end_date,
        "budget_amount": item.budget_amount,
        "budget_currency": item.budget_currency,
        "notes": item.notes,
        "is_archived": item.is_archived,
        "archived_at": item.archived_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def shipment_detail_payload(item: Shipment) -> dict:
    return {
        "id": item.id,
        "shipping_address_id": item.shipping_address_id,
        "recipient_address": item.recipient_address,
        "oa_pi_number": item.oa_pi_number,
        "tracking_number": item.tracking_number,
        "carrier": item.carrier,
        "status": item.status,
        "shipped_at": item.shipped_at,
        "delivered_at": item.delivered_at,
        "notes": item.notes,
        "items": [{"id": row.id, "product_id": row.product_id, "product_name": row.product_name, "quantity": row.quantity, "unit_cost": row.unit_cost} for row in item.items],
    }


def validate_shipping_address_links(db: Session, media_id: int, contact_id: int | None) -> None:
    if not db.get(Media, media_id):
        raise HTTPException(404, "Media not found")
    if contact_id:
        contact = db.get(Contact, contact_id)
        if not contact or contact.media_id != media_id:
            raise HTTPException(400, "Contact does not belong to the selected media")


def set_default_shipping_address(db: Session, item: ShippingAddress) -> None:
    db.query(ShippingAddress).filter(
        ShippingAddress.media_id == item.media_id,
        ShippingAddress.id != item.id,
    ).update({ShippingAddress.is_default: False}, synchronize_session=False)
    item.is_default = True


def format_shipping_address(item: ShippingAddress) -> str:
    parts = [
        item.recipient_name,
        item.phone,
        item.email,
        item.address_text,
        " ".join(value for value in [item.city, item.region, item.postal_code, item.country] if value),
        f"税号/清关号: {item.tax_or_customs_number}" if item.tax_or_customs_number else None,
        item.shipping_notes,
    ]
    return "\n".join(str(value).strip() for value in parts if value and str(value).strip())


def apply_shipping_address_snapshot(db: Session, media_id: int, data: dict[str, Any]) -> None:
    address_id = data.get("shipping_address_id")
    if not address_id:
        return
    address = db.get(ShippingAddress, address_id)
    if not address or address.media_id != media_id:
        raise HTTPException(400, "Shipping address does not belong to the selected media")
    if not data.get("recipient_address"):
        data["recipient_address"] = format_shipping_address(address)


def campaign_detail_payload(item: Campaign) -> dict:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "media_id": item.media_id,
        "owner_id": item.owner_id,
        "collaboration_type": item.collaboration_type,
        "execution_status": item.execution_status,
        "expected_publish_date": item.expected_publish_date,
        "next_action": item.next_action,
        "follow_up_date": item.follow_up_date,
        "follow_up_priority": item.follow_up_priority,
        "follow_up_done": item.follow_up_done,
        "notes": item.notes,
        "media": media_summary_payload(item.media),
        "owner": user_summary_payload(item.owner),
        "shipments": [shipment_detail_payload(shipment) for shipment in item.shipments],
        "deliverables": [{"id": row.id, "url": row.url, "deliverable_type": row.deliverable_type, "published_at": row.published_at, "impressions": row.impressions, "views": row.views, "likes": row.likes, "comments": row.comments} for row in item.deliverables],
        "cost_items": [{"id": row.id, "cost_type": row.cost_type, "planned_amount": row.planned_amount, "actual_amount": row.actual_amount, "currency": row.currency, "payment_status": row.payment_status} for row in item.cost_items],
        "activities": [{"id": row.id, "activity_type": row.activity_type, "content": row.content, "created_at": row.created_at} for row in item.activities],
    }


def project_result_summary(item: Project) -> dict[str, Any]:
    campaigns = item.campaigns
    deliverables = [deliverable for campaign in campaigns for deliverable in campaign.deliverables]
    actual = sum(cost.actual_amount or 0 for campaign in campaigns for cost in campaign.cost_items)
    impressions = sum(deliverable.impressions or 0 for deliverable in deliverables)
    views = sum(deliverable.views or 0 for deliverable in deliverables)
    likes = sum(deliverable.likes or 0 for deliverable in deliverables)
    comments = sum(deliverable.comments or 0 for deliverable in deliverables)
    reach = impressions or views
    published = sum(1 for campaign in campaigns if campaign.execution_status in {"已发布", "已结算"} or campaign.deliverables)
    return {
        "collaboration_count": len(campaigns),
        "published_count": published,
        "completion_rate": round(published / len(campaigns) * 100, 1) if campaigns else 0,
        "actual_amount": actual,
        "deliverable_count": len(deliverables),
        "impressions": impressions,
        "views": views,
        "likes": likes,
        "comments": comments,
        "cpm_base": "曝光" if impressions else ("播放/阅读" if views else None),
        "cpm": round(actual / reach * 1000, 2) if reach else None,
    }


@app.get("/api/projects/{item_id}/summary")
def project_summary(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    item = db.query(Project).options(joinedload(Project.campaigns).joinedload(Campaign.media), joinedload(Project.campaigns).joinedload(Campaign.deliverables), joinedload(Project.campaigns).joinedload(Campaign.cost_items)).filter(Project.id == item_id).first()
    if not item:
        raise HTTPException(404, "Project not found")
    return project_result_summary(item)


@app.get("/api/projects/{item_id}/report.xlsx")
def export_project_report(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    item = db.query(Project).options(joinedload(Project.campaigns).joinedload(Campaign.media), joinedload(Project.campaigns).joinedload(Campaign.deliverables), joinedload(Project.campaigns).joinedload(Campaign.cost_items)).filter(Project.id == item_id).first()
    if not item:
        raise HTTPException(404, "Project not found")
    summary = project_result_summary(item)
    book = Workbook()
    overview = book.active
    overview.title = "项目成果摘要"
    overview.append(["项目", item.name])
    overview.append(["项目编号", item.project_code or ""])
    overview.append(["合作对象数", summary["collaboration_count"]])
    overview.append(["已发布", summary["published_count"]])
    overview.append(["完成率", summary["completion_rate"] / 100])
    overview.append(["实付", summary["actual_amount"]])
    overview.append(["总曝光", summary["impressions"]])
    overview.append(["总播放/阅读", summary["views"]])
    overview.append(["总互动", summary["likes"] + summary["comments"]])
    overview.append(["CPM", summary["cpm"] if summary["cpm"] is not None else "待补充曝光/播放数据"])
    overview["A1"].font = Font(bold=True, color="FFFFFF")
    overview["B1"].font = Font(bold=True, color="FFFFFF")
    overview["A1"].fill = PatternFill("solid", fgColor="1B8D82")
    overview["B1"].fill = PatternFill("solid", fgColor="1B8D82")
    overview.column_dimensions["A"].width = 22
    overview.column_dimensions["B"].width = 34
    overview["B5"].number_format = "0.0%"
    overview["B6"].number_format = '#,##0.00'
    overview["B10"].number_format = '#,##0.00'
    details = book.create_sheet("合作明细")
    details.append(["媒体/KOL", "执行状态", "内容链接", "发布时间", "曝光", "播放/阅读", "点赞", "评论", "实付"])
    for campaign in item.campaigns:
        cost = sum(row.actual_amount or 0 for row in campaign.cost_items)
        if campaign.deliverables:
            for deliverable in campaign.deliverables:
                details.append([campaign.media.name if campaign.media else "", campaign.execution_status, deliverable.url or "", deliverable.published_at, deliverable.impressions or 0, deliverable.views or 0, deliverable.likes or 0, deliverable.comments or 0, cost])
        else:
            details.append([campaign.media.name if campaign.media else "", campaign.execution_status, "", "", 0, 0, 0, 0, cost])
    for cell in details[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1B8D82")
    for column, width in {"A": 24, "B": 16, "C": 40, "D": 14, "E": 12, "F": 14, "G": 12, "H": 12, "I": 14}.items():
        details.column_dimensions[column].width = width
    stream = BytesIO()
    book.save(stream)
    stream.seek(0)
    filename = f"{item.name}_项目复盘.xlsx"
    disposition = f"attachment; filename=project-report.xlsx; filename*=UTF-8''{quote(filename)}"
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": disposition})


@app.put("/api/projects/{item_id}", response_model=ProjectOut)
def update_project(item_id: int, payload: ProjectBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.get(Project, item_id)
    if not item:
        raise HTTPException(404, "Project not found")
    if payload.project_code and db.query(Project).filter(Project.project_code == payload.project_code, Project.id != item_id).first():
        raise HTTPException(400, "Project code already exists")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/projects/{item_id}")
def delete_project(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    item = db.query(Project).options(joinedload(Project.campaigns).joinedload(Campaign.shipments), joinedload(Project.campaigns).joinedload(Campaign.cost_items), joinedload(Project.campaigns).joinedload(Campaign.deliverables), joinedload(Project.campaigns).joinedload(Campaign.activities)).filter(Project.id == item_id).first()
    if not item:
        raise HTTPException(404, "Project not found")
    deleted_campaigns = len(item.campaigns)
    deleted_shipments = sum(len(campaign.shipments) for campaign in item.campaigns)
    deleted_cost_items = sum(len(campaign.cost_items) for campaign in item.campaigns)
    deleted_deliverables = sum(len(campaign.deliverables) for campaign in item.campaigns)
    deleted_activities = sum(len(campaign.activities) for campaign in item.campaigns)
    for campaign in list(item.campaigns):
        db.delete(campaign)
    db.flush()
    db.delete(item)
    db.commit()
    return {"ok": True, "deleted_campaigns": deleted_campaigns, "deleted_shipments": deleted_shipments, "deleted_cost_items": deleted_cost_items, "deleted_deliverables": deleted_deliverables, "deleted_activities": deleted_activities}


@app.post("/api/projects/{item_id}/archive")
def archive_project(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    item = db.get(Project, item_id)
    if not item:
        raise HTTPException(404, "Project not found")
    item.is_archived = True
    item.archived_at = datetime.now()
    db.commit()
    return {"ok": True, "id": item.id}


@app.post("/api/projects/{item_id}/restore")
def restore_project(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    item = db.get(Project, item_id)
    if not item:
        raise HTTPException(404, "Project not found")
    if item.name.startswith(HISTORICAL_PROJECT_PREFIX):
        raise HTTPException(400, "Imported historical projects cannot be restored")
    item.is_archived = False
    item.archived_at = None
    db.commit()
    return {"ok": True, "id": item.id}


@app.post("/api/shipments", response_model=ShipmentOut)
def create_shipment(payload: ShipmentBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    data = payload.model_dump(exclude={"items"})
    campaign = db.get(Campaign, payload.campaign_id)
    if not campaign:
        raise HTTPException(404, "Collaboration not found")
    apply_shipping_address_snapshot(db, campaign.media_id, data)
    item = Shipment(**data)
    db.add(item)
    db.flush()
    for row in payload.items:
        db.add(ShipmentItem(shipment_id=item.id, **row.model_dump()))
    db.commit()
    db.refresh(item)
    return item


@app.post("/api/projects/{project_id}/shipments", response_model=ShipmentOut)
def create_project_shipment(project_id: int, payload: ProjectShipmentBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    project = db.get(Project, project_id)
    media = db.get(Media, payload.media_id)
    if not project or not media:
        raise HTTPException(404, "Project or media not found")
    if payload.campaign_id:
        campaign = db.get(Campaign, payload.campaign_id)
        if not campaign or campaign.project_id != project_id or campaign.media_id != payload.media_id:
            raise HTTPException(400, "Selected collaboration does not belong to this project and media")
    else:
        campaign = db.query(Campaign).filter(Campaign.project_id == project_id, Campaign.media_id == payload.media_id, Campaign.execution_status.notin_(["已发布", "已结算", "已暂停/取消"])).order_by(Campaign.updated_at.desc()).first()
    if not campaign:
        campaign = Campaign(project_id=project_id, media_id=payload.media_id, owner_id=payload.owner_id, execution_status="待发货", stage="Not Started", sample_status="Not Sent")
        db.add(campaign)
        db.flush()
    elif campaign.execution_status not in {"已发布", "已结算", "已暂停/取消"} and payload.status in SHIPMENT_STATUS_PROGRESS:
        current_progress = SHIPMENT_STATUS_PROGRESS.get(campaign.execution_status, 0)
        next_progress = SHIPMENT_STATUS_PROGRESS.get(payload.status, current_progress)
        if next_progress > current_progress:
            campaign.execution_status = payload.status
    data = payload.model_dump(exclude={"items", "media_id", "campaign_id", "owner_id"})
    apply_shipping_address_snapshot(db, payload.media_id, data)
    shipment = Shipment(campaign_id=campaign.id, **data)
    db.add(shipment)
    db.flush()
    for row in payload.items:
        item_data = row.model_dump()
        if item_data.get("product_id"):
            product = db.get(Product, item_data["product_id"])
            if not product:
                raise HTTPException(400, "Product not found")
            item_data["product_name"] = product.model
            ensure_project_link(db, project_id, product.id)
        elif item_data.get("product_name"):
            product = find_or_create_product(db, item_data["product_name"], "项目寄样时创建")
            item_data["product_id"] = product.id
            item_data["product_name"] = product.model
            ensure_project_link(db, project_id, product.id)
        db.add(ShipmentItem(shipment_id=shipment.id, **item_data))
    db.commit()
    db.refresh(shipment)
    return shipment


@app.post("/api/cost-items", response_model=CostItemOut)
def create_cost_item(payload: CostItemBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = CostItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.post("/api/activities", response_model=ActivityOut)
def create_activity(payload: ActivityBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = Activity(**payload.model_dump(), user_id=user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/campaigns", response_model=dict)
def list_campaigns(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    product_id: int | None = None,
    media_id: int | None = None,
    country: str | None = None,
    stage: str | None = None,
    sample_status: str | None = None,
    owner_id: int | None = None,
    history_only: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    query = db.query(Campaign).options(joinedload(Campaign.project), joinedload(Campaign.product), joinedload(Campaign.media), joinedload(Campaign.owner)).outerjoin(Project)
    if history_only:
        query = query.filter(or_(Campaign.is_historical.is_(True), Project.is_archived.is_(True), Project.name.like(f"{HISTORICAL_PROJECT_PREFIX}%")))
    else:
        query = query.filter(Campaign.is_historical.is_(False), or_(Campaign.project_id.is_(None), and_(Project.is_archived.is_(False), ~Project.name.like(f"{HISTORICAL_PROJECT_PREFIX}%"))))
    if product_id:
        query = query.filter(Campaign.product_id == product_id)
    if media_id:
        query = query.filter(Campaign.media_id == media_id)
    if country:
        query = query.join(Media).filter(Media.country == country)
    if stage:
        query = query.filter(Campaign.stage == stage)
    if sample_status:
        query = query.filter(Campaign.sample_status == sample_status)
    if owner_id:
        query = query.filter(Campaign.owner_id == owner_id)
    return list_payload(query.order_by(Campaign.updated_at.desc()), page, page_size)


@app.get("/api/collaborations/{item_id:int}")
def collaboration_detail(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    item = db.query(Campaign).options(joinedload(Campaign.project), joinedload(Campaign.media).joinedload(Media.contacts), joinedload(Campaign.owner), joinedload(Campaign.shipments).joinedload(Shipment.items), joinedload(Campaign.deliverables), joinedload(Campaign.cost_items), joinedload(Campaign.activities).joinedload(Activity.user)).filter(Campaign.id == item_id).first()
    if not item:
        raise HTTPException(404, "Collaboration not found")
    return item


@app.patch("/api/collaborations/{item_id:int}")
def patch_collaboration(item_id: int, payload: CollaborationPatch, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.query(Campaign).options(joinedload(Campaign.shipments)).filter(Campaign.id == item_id).first()
    if not item:
        raise HTTPException(404, "Collaboration not found")
    data = payload.model_dump(exclude_unset=True)
    for key in ["project_id", "media_id", "owner_id", "collaboration_type", "expected_publish_date", "notes", "next_action", "follow_up_date", "follow_up_priority", "follow_up_done"]:
        if key in data:
            setattr(item, key, data[key])
    if "execution_status" in data:
        if data["execution_status"] not in EXECUTION_STATUSES:
            raise HTTPException(400, "Invalid execution status")
        item.execution_status = data["execution_status"]
        if item.execution_status == "已发布":
            item.stage = "Published"
        elif item.execution_status == "已暂停/取消":
            item.stage = "Paused"
        db.add(Activity(campaign_id=item.id, user_id=user.id, activity_type="状态更新", content=f"执行状态更新为：{item.execution_status}"))
    if data.get("follow_up_done") is True:
        db.add(Activity(campaign_id=item.id, user_id=user.id, activity_type="待办完成", content=f"已完成待办：{item.next_action or '未填写下一步动作'}"))
    if "tracking_number" in data:
        shipment = item.shipments[0] if item.shipments else Shipment(campaign_id=item.id, status=item.execution_status)
        if not item.shipments:
            db.add(shipment)
        shipment.tracking_number = data["tracking_number"]
        if "execution_status" in data:
            shipment.status = item.execution_status
    db.commit()
    refreshed = db.query(Campaign).options(joinedload(Campaign.project), joinedload(Campaign.media), joinedload(Campaign.owner), joinedload(Campaign.shipments)).filter(Campaign.id == item_id).first()
    return {
        "id": refreshed.id,
        "project_id": refreshed.project_id,
        "project_name": refreshed.project.name if refreshed.project else "未归属项目",
        "media_id": refreshed.media_id,
        "media_name": refreshed.media.name if refreshed.media else None,
        "owner_id": refreshed.owner_id,
        "owner": refreshed.owner.name if refreshed.owner else None,
        "execution_status": refreshed.execution_status,
        "expected_publish_date": refreshed.expected_publish_date,
        "next_action": refreshed.next_action,
        "follow_up_date": refreshed.follow_up_date,
        "follow_up_priority": refreshed.follow_up_priority,
        "follow_up_done": refreshed.follow_up_done,
        "tracking_number": refreshed.shipments[0].tracking_number if refreshed.shipments else None,
        "notes": refreshed.notes,
    }


@app.patch("/api/collaborations/bulk")
def bulk_patch_collaborations(payload: CollaborationBulkPatch, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    ids = list(dict.fromkeys(payload.ids))
    if not ids:
        raise HTTPException(400, "请选择至少一条执行单")
    data = payload.model_dump(exclude_unset=True, exclude={"ids"})
    if not data:
        raise HTTPException(400, "请选择要修改的字段")
    if data.get("execution_status") and data["execution_status"] not in EXECUTION_STATUSES:
        raise HTTPException(400, "Invalid execution status")
    items = db.query(Campaign).filter(Campaign.id.in_(ids)).all()
    for item in items:
        for key, value in data.items():
            setattr(item, key, value)
        if data.get("execution_status") == "已发布":
            item.stage = "Published"
        elif data.get("execution_status") == "已暂停/取消":
            item.stage = "Paused"
        db.add(Activity(campaign_id=item.id, user_id=user.id, activity_type="批量更新", content="已通过工作台批量更新"))
    db.commit()
    return {"updated": len(items)}


@app.post("/api/campaigns", response_model=CampaignOut)
def create_campaign(payload: CampaignBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    validate_campaign(payload)
    item = Campaign(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/campaigns/{item_id}", response_model=CampaignOut)
def update_campaign(item_id: int, payload: CampaignBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    validate_campaign(payload)
    item = db.get(Campaign, item_id)
    if not item:
        raise HTTPException(404, "Campaign not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/campaigns/{item_id}")
def delete_campaign(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    item = db.query(Campaign).options(joinedload(Campaign.shipments), joinedload(Campaign.cost_items), joinedload(Campaign.deliverables), joinedload(Campaign.activities)).filter(Campaign.id == item_id).first()
    if not item:
        raise HTTPException(404, "Campaign not found")
    counts = {"deleted_shipments": len(item.shipments), "deleted_cost_items": len(item.cost_items), "deleted_deliverables": len(item.deliverables), "deleted_activities": len(item.activities)}
    db.delete(item)
    db.commit()
    return {"ok": True, **counts}


@app.post("/api/campaigns/{item_id}/archive")
def archive_campaign(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    item = db.get(Campaign, item_id)
    if not item:
        raise HTTPException(404, "Campaign not found")
    item.is_historical = True
    item.archived_at = datetime.now()
    db.commit()
    return {"ok": True, "id": item.id}


@app.post("/api/campaigns/{item_id}/restore")
def restore_campaign(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))]):
    item = db.query(Campaign).options(joinedload(Campaign.project)).filter(Campaign.id == item_id).first()
    if not item:
        raise HTTPException(404, "Campaign not found")
    if not item.archived_at:
        raise HTTPException(400, "Imported historical collaborations cannot be restored")
    if item.project and item.project.is_archived:
        raise HTTPException(400, "Restore the project before restoring this collaboration")
    item.is_historical = False
    item.archived_at = None
    db.commit()
    return {"ok": True, "id": item.id}


@app.get("/api/deliverables", response_model=dict)
def list_deliverables(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    product_id: int | None = None,
    media_id: int | None = None,
    deliverable_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    query = db.query(Deliverable).options(joinedload(Deliverable.campaign).joinedload(Campaign.product), joinedload(Deliverable.campaign).joinedload(Campaign.media))
    query = query.join(Campaign)
    if product_id:
        query = query.filter(Campaign.product_id == product_id)
    if media_id:
        query = query.filter(Campaign.media_id == media_id)
    if deliverable_type:
        query = query.filter(Deliverable.deliverable_type == deliverable_type)
    if date_from:
        query = query.filter(Deliverable.published_at >= date_from)
    if date_to:
        query = query.filter(Deliverable.published_at <= date_to)
    return list_payload(query.order_by(Deliverable.published_at.desc().nullslast()), page, page_size)


@app.post("/api/deliverables", response_model=DeliverableOut)
def create_deliverable(payload: DeliverableBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    if payload.deliverable_type not in DELIVERABLE_TYPES:
        raise HTTPException(400, "Invalid deliverable type")
    item = Deliverable(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/deliverables/{item_id}", response_model=DeliverableOut)
def update_deliverable(item_id: int, payload: DeliverableBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.get(Deliverable, item_id)
    if not item:
        raise HTTPException(404, "Deliverable not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/contacts", response_model=dict)
def list_contacts(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)], q: str | None = None, media_id: int | None = None, country: str | None = None, page: int = 1, page_size: int = 20):
    query = db.query(Contact).options(joinedload(Contact.media)).join(Media)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Contact.name.ilike(like), Contact.email.ilike(like), Contact.notes.ilike(like), Media.name.ilike(like)))
    if media_id:
        query = query.filter(Contact.media_id == media_id)
    if country:
        query = query.filter(Media.country == country)
    return list_payload(query.order_by(Contact.id.desc()), page, page_size)


@app.post("/api/contacts", response_model=ContactOut)
def create_contact(payload: ContactBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    if not db.get(Media, payload.media_id):
        raise HTTPException(404, "Media not found")
    if payload.is_primary:
        db.query(Contact).filter(Contact.media_id == payload.media_id).update({Contact.is_primary: False}, synchronize_session=False)
    item = Contact(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/contacts/{item_id}", response_model=ContactOut)
def update_contact(item_id: int, payload: ContactBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.get(Contact, item_id)
    if not item:
        raise HTTPException(404, "Contact not found")
    if not db.get(Media, payload.media_id):
        raise HTTPException(404, "Media not found")
    if payload.is_primary:
        db.query(Contact).filter(Contact.media_id == payload.media_id, Contact.id != item_id).update({Contact.is_primary: False}, synchronize_session=False)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/contacts/{item_id}")
def delete_contact(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.get(Contact, item_id)
    if not item:
        raise HTTPException(404, "Contact not found")
    db.query(ShippingAddress).filter(ShippingAddress.contact_id == item_id).update({ShippingAddress.contact_id: None}, synchronize_session=False)
    db.delete(item)
    db.commit()
    return {"ok": True}


@app.get("/api/media/{media_id}/shipping-addresses", response_model=list[ShippingAddressOut])
def list_shipping_addresses(media_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(current_user)]):
    if not db.get(Media, media_id):
        raise HTTPException(404, "Media not found")
    return db.query(ShippingAddress).filter(ShippingAddress.media_id == media_id).order_by(ShippingAddress.is_default.desc(), ShippingAddress.updated_at.desc()).all()


@app.post("/api/shipping-addresses", response_model=ShippingAddressOut)
def create_shipping_address(payload: ShippingAddressBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    validate_shipping_address_links(db, payload.media_id, payload.contact_id)
    item = ShippingAddress(**payload.model_dump())
    db.add(item)
    db.flush()
    has_default = db.query(ShippingAddress.id).filter(ShippingAddress.media_id == payload.media_id, ShippingAddress.is_default.is_(True), ShippingAddress.id != item.id).first()
    if payload.is_default or not has_default:
        set_default_shipping_address(db, item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/api/shipping-addresses/{item_id}", response_model=ShippingAddressOut)
def update_shipping_address(item_id: int, payload: ShippingAddressBase, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.get(ShippingAddress, item_id)
    if not item:
        raise HTTPException(404, "Shipping address not found")
    validate_shipping_address_links(db, payload.media_id, payload.contact_id)
    old_media_id = item.media_id
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    if payload.is_default:
        set_default_shipping_address(db, item)
    db.flush()
    if old_media_id != item.media_id and not db.query(ShippingAddress.id).filter(ShippingAddress.media_id == old_media_id, ShippingAddress.is_default.is_(True)).first():
        fallback = db.query(ShippingAddress).filter(ShippingAddress.media_id == old_media_id).order_by(ShippingAddress.updated_at.desc()).first()
        if fallback:
            fallback.is_default = True
    db.commit()
    db.refresh(item)
    return item


@app.post("/api/shipping-addresses/{item_id}/default", response_model=ShippingAddressOut)
def make_default_shipping_address(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.get(ShippingAddress, item_id)
    if not item:
        raise HTTPException(404, "Shipping address not found")
    set_default_shipping_address(db, item)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/shipping-addresses/{item_id}")
def delete_shipping_address(item_id: int, db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    item = db.get(ShippingAddress, item_id)
    if not item:
        raise HTTPException(404, "Shipping address not found")
    media_id, was_default = item.media_id, item.is_default
    db.query(Shipment).filter(Shipment.shipping_address_id == item_id).update({Shipment.shipping_address_id: None}, synchronize_session=False)
    db.delete(item)
    db.flush()
    if was_default:
        fallback = db.query(ShippingAddress).filter(ShippingAddress.media_id == media_id).order_by(ShippingAddress.updated_at.desc()).first()
        if fallback:
            fallback.is_default = True
    db.commit()
    return {"ok": True}


def parse_address_candidate(raw: str, country: str | None = None) -> dict[str, Any]:
    email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", raw)
    phone = re.search(r"(?:\+?\d[\d\s().-]{6,}\d)", raw)
    postal = re.search(r"(?i)(?:zip|postal(?:\s*code)?|邮编)\s*[:：]?\s*([A-Z0-9 -]{3,12})", raw)
    recipient = re.search(r"(?i)(?:recipient|receiver|contact|收件人|姓名)\s*[:：]\s*([^\n,;]+)", raw)
    return {
        "recipient_name": recipient.group(1).strip() if recipient else None,
        "phone": phone.group(0).strip() if phone else None,
        "email": email.group(0) if email else None,
        "address_text": raw.strip(),
        "postal_code": postal.group(1).strip() if postal else None,
        "country": country,
        "source_text": raw.strip(),
        "is_confirmed": True,
    }


@app.get("/api/address-import/candidates")
def address_import_candidates(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(editable_user)]):
    source = ROOT / "outputs" / "cleaning" / "铭瑄红人记者库_cleaned.xlsx.inspect.ndjson"
    if not source.exists():
        return {"source_available": False, "items": []}
    keywords = re.compile(r"(?i)address|street|road|avenue|building|floor|postal|zip|地址|邮编|收件|省|市|区")
    source_rows: list[dict[str, Any]] = []
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                block = json.loads(line)
            except json.JSONDecodeError:
                continue
            if block.get("kind") != "table" or block.get("sheet") != "Raw 原始数据":
                continue
            values = block.get("values") or []
            if not values:
                continue
            headers = [str(value or "") for value in values[0]]
            for row in values[1:]:
                source_rows.append({headers[index]: row[index] if index < len(row) else None for index in range(len(headers))})
    items: list[dict[str, Any]] = []
    for row_number, flat in enumerate(source_rows, 2):
        raw = str(flat.get("联系方式") or "").strip()
        if not raw or not keywords.search(raw):
            continue
        media_name = str(flat.get("名字") or flat.get("名称") or "").strip()
        country = str(flat.get("国家") or "").strip() or None
        contact_name = str(flat.get("联系人&职位") or flat.get("联系人") or "").strip()
        media = db.query(Media).filter(func.lower(Media.name) == media_name.lower()).first() if media_name else None
        contact = None
        if media and contact_name:
            contact = db.query(Contact).filter(Contact.media_id == media.id, Contact.name.ilike(f"%{contact_name.split('/')[0].strip()}%")).first()
        imported = db.query(ShippingAddress.id).filter(ShippingAddress.source_text == raw).first() is not None
        items.append({"id": f"row-{row_number}", "media_name": media_name, "contact_name": contact_name, "raw_text": raw, "media_id": media.id if media else None, "contact_id": contact.id if contact else None, "imported": imported, "parsed": parse_address_candidate(raw, country)})
    return {"source_available": True, "items": items}


@app.get("/api/dashboard")
def dashboard(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    product_model: str | None = None,
    country: str | None = None,
    platform_type: str | None = None,
    stage: str | None = None,
    sample_status: str | None = None,
    owner_id: int | None = None,
    has_deliverable: bool | None = None,
):
    base = db.query(Campaign).options(joinedload(Campaign.product), joinedload(Campaign.media), joinedload(Campaign.owner), joinedload(Campaign.deliverables))
    if product_model:
        like = f"%{product_model}%"
        base = base.join(Product, isouter=True).filter(or_(Product.model.ilike(like), Product.full_name.ilike(like), Product.aliases.ilike(like)))
    if country or platform_type:
        base = base.join(Media)
    if country:
        base = base.filter(Media.country == country)
    if platform_type:
        base = base.filter(Media.platform_type == platform_type)
    if stage:
        base = base.filter(Campaign.stage == stage)
    if sample_status:
        base = base.filter(Campaign.sample_status == sample_status)
    if owner_id:
        base = base.filter(Campaign.owner_id == owner_id)
    if has_deliverable is True:
        base = base.join(Deliverable)
    elif has_deliverable is False:
        base = base.outerjoin(Deliverable).filter(Deliverable.id.is_(None))
    campaigns = base.order_by(Campaign.updated_at.desc()).limit(200).all()
    now_count = lambda condition: db.query(func.count(Campaign.id)).filter(condition).scalar() or 0
    kpis = {
        "media_total": db.query(func.count(Media.id)).scalar() or 0,
        "product_total": db.query(func.count(Product.id)).scalar() or 0,
        "campaign_total": db.query(func.count(Campaign.id)).scalar() or 0,
        "contacted_total": now_count(Campaign.stage.in_(["Contacted", "Waiting Reply", "Quoting", "Brief Sent", "Sample Sent", "In Production", "Published"])),
        "brief_sent_total": now_count(Campaign.brief_sent.is_(True)),
        "sample_sent_total": now_count(Campaign.sample_status.in_(["Shipped", "In Transit", "Customs Clearance", "Delivered"])),
        "in_production_total": now_count(Campaign.stage == "In Production"),
        "published_total": now_count(Campaign.stage == "Published"),
        "overdue_total": db.query(func.count(Campaign.id)).filter(and_(Campaign.expected_publish_date < func.date("now"), Campaign.actual_publish_date.is_(None))).scalar() or 0,
    }
    rows = []
    for campaign in campaigns:
        first_deliverable = campaign.deliverables[0] if campaign.deliverables else None
        rows.append(
            {
                "id": campaign.id,
                "product_model": campaign.product.model if campaign.product else None,
                "media_name": campaign.media.name if campaign.media else None,
                "country": campaign.media.country if campaign.media else None,
                "platform_type": campaign.media.platform_type if campaign.media else None,
                "owner": campaign.owner.name if campaign.owner else None,
                "stage": campaign.stage,
                "sample_status": campaign.sample_status,
                "brief_sent": campaign.brief_sent,
                "expected_publish_date": campaign.expected_publish_date,
                "actual_publish_date": campaign.actual_publish_date,
                "deliverable_url": first_deliverable.url if first_deliverable else None,
                "views": first_deliverable.views if first_deliverable else None,
            }
        )
    return {"kpis": kpis, "items": rows}


@app.get("/api/workbench")
def workbench(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    project_id: int | None = None,
    owner_id: int | None = None,
    execution_status: str | None = None,
    country: str | None = None,
    platform_type: str | None = None,
    queue: str = "today",
):
    query = db.query(Campaign).options(joinedload(Campaign.project), joinedload(Campaign.media), joinedload(Campaign.owner), joinedload(Campaign.shipments), joinedload(Campaign.deliverables), joinedload(Campaign.cost_items)).outerjoin(Project).filter(Campaign.is_historical.is_(False), or_(Campaign.project_id.is_(None), and_(Project.is_archived.is_(False), ~Project.name.like(f"{HISTORICAL_PROJECT_PREFIX}%"))))
    if project_id:
        query = query.filter(Campaign.project_id == project_id)
    if owner_id:
        query = query.filter(Campaign.owner_id == owner_id)
    if execution_status:
        query = query.filter(Campaign.execution_status == execution_status)
    if country or platform_type:
        query = query.join(Media)
    if country:
        query = query.filter(Media.country == country)
    if platform_type:
        query = query.filter(Media.platform_type == platform_type)
    today_date = date.today()
    if queue == "overdue":
        query = query.filter(Campaign.follow_up_done.is_(False), Campaign.follow_up_date < today_date)
    elif queue == "today":
        query = query.filter(Campaign.follow_up_done.is_(False), Campaign.follow_up_date == today_date)
    elif queue == "upcoming":
        query = query.filter(Campaign.follow_up_done.is_(False), Campaign.follow_up_date > today_date, Campaign.follow_up_date <= today_date + timedelta(days=7))
    elif queue != "all":
        raise HTTPException(400, "Invalid queue")
    items = query.order_by(Campaign.follow_up_date.asc().nullslast(), Campaign.updated_at.desc()).limit(300).all()
    today = func.date("now")
    visible_campaigns = db.query(Campaign.id).outerjoin(Project).filter(Campaign.is_historical.is_(False), or_(Campaign.project_id.is_(None), and_(Project.is_archived.is_(False), ~Project.name.like(f"{HISTORICAL_PROJECT_PREFIX}%"))))
    overdue = visible_campaigns.filter(Campaign.expected_publish_date < today, Campaign.actual_publish_date.is_(None), Campaign.execution_status.notin_(["已发布", "已结算", "已暂停/取消"])).count()
    all_costs = db.query(CostItem).join(Campaign).outerjoin(Project).filter(Campaign.is_historical.is_(False), or_(Campaign.project_id.is_(None), and_(Project.is_archived.is_(False), ~Project.name.like(f"{HISTORICAL_PROJECT_PREFIX}%")))).all()
    rows = []
    for item in items:
        actual = sum(cost.actual_amount or 0 for cost in item.cost_items)
        planned = sum(cost.planned_amount or 0 for cost in item.cost_items)
        pending_payment = any(cost.payment_status in ["未付款", "部分付款"] for cost in item.cost_items)
        rows.append({
            "id": item.id,
            "project_id": item.project_id,
            "project_name": item.project.name if item.project else "未归属项目",
            "media_name": item.media.name if item.media else None,
            "country": item.media.country if item.media else None,
            "platform_type": item.media.platform_type if item.media else None,
            "owner": item.owner.name if item.owner else None,
            "execution_status": item.execution_status,
            "next_action": item.next_action,
            "follow_up_date": item.follow_up_date,
            "follow_up_priority": item.follow_up_priority,
            "follow_up_done": item.follow_up_done,
            "expected_publish_date": item.expected_publish_date,
            "tracking_number": item.shipments[0].tracking_number if item.shipments else None,
            "actual_amount": actual,
            "planned_amount": planned,
            "pending_payment": pending_payment,
            "content_url": item.deliverables[0].url if item.deliverables else None,
        })
    return {
        "kpis": {
            "project_total": db.query(func.count(Project.id)).scalar() or 0,
            "collaboration_total": len(items),
            "pending_shipping": sum(1 for item in items if item.execution_status == "待发货"),
            "in_transit": sum(1 for item in items if item.execution_status == "运输中"),
            "awaiting_content": sum(1 for item in items if item.execution_status == "已签收待产出"),
            "published": sum(1 for item in items if item.execution_status == "已发布"),
            "overdue_content": overdue,
            "actual_amount": sum(cost.actual_amount or 0 for cost in all_costs),
            "pending_payment": sum(1 for item in items if any(cost.payment_status in ["未付款", "部分付款"] for cost in item.cost_items)),
            "overdue_tasks": db.query(func.count(Campaign.id)).filter(Campaign.follow_up_done.is_(False), Campaign.follow_up_date < today_date).scalar() or 0,
            "today_tasks": db.query(func.count(Campaign.id)).filter(Campaign.follow_up_done.is_(False), Campaign.follow_up_date == today_date).scalar() or 0,
            "upcoming_tasks": db.query(func.count(Campaign.id)).filter(Campaign.follow_up_done.is_(False), Campaign.follow_up_date > today_date, Campaign.follow_up_date <= today_date + timedelta(days=7)).scalar() or 0,
        },
        "items": rows,
    }


@app.post("/api/import/preview")
async def import_preview(user: Annotated[User, Depends(require_roles("Admin"))], file: UploadFile = File(...)):
    result = preview_import(await file.read())
    return result.__dict__


@app.post("/api/import/confirm")
async def import_confirm(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))], file: UploadFile = File(...)):
    result = confirm_import(db, await file.read())
    return result.__dict__


@app.post("/api/execution-import/preview")
async def execution_import_preview(user: Annotated[User, Depends(require_roles("Admin"))], file: UploadFile = File(...)):
    return preview_execution_import(await file.read())


@app.post("/api/execution-import/confirm")
async def execution_import_confirm(db: Annotated[Session, Depends(get_db)], user: Annotated[User, Depends(require_roles("Admin"))], file: UploadFile = File(...)):
    return confirm_execution_import(db, await file.read())


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{path:path}")
def spa(path: str):
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Frontend is not built yet. Run start.bat or build the frontend."}
