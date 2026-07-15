from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    email: str
    password: str
    name: str
    role: str = "Viewer"


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime


class MediaBase(BaseModel):
    name: str
    country: str | None = None
    region: str | None = None
    category: str | None = None
    platform_type: str | None = None
    website_url: str | None = None
    followers_or_traffic: int | None = None
    media_tier: str | None = None
    cooperation_status: str | None = None
    notes: str | None = None


class MediaOut(MediaBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ContactBase(BaseModel):
    media_id: int
    name: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    telegram: str | None = None
    brief_email: str | None = None
    press_release_email: str | None = None
    is_primary: bool = False
    notes: str | None = None


class ContactOut(ContactBase, ORMModel):
    id: int


class ShippingAddressBase(BaseModel):
    media_id: int
    contact_id: int | None = None
    recipient_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address_text: str
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country: str | None = None
    tax_or_customs_number: str | None = None
    shipping_notes: str | None = None
    source_text: str | None = None
    is_default: bool = False
    is_confirmed: bool = True


class ShippingAddressOut(ShippingAddressBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ProductBase(BaseModel):
    model: str
    full_name: str | None = None
    product_line: str | None = None
    platform: str | None = None
    aliases: str | None = None
    launch_status: str | None = None
    notes: str | None = None
    project_ids: list[int] = []


class ProductOut(ProductBase, ORMModel):
    id: int


class ProductMergeIn(BaseModel):
    target_product_id: int


class ProjectBase(BaseModel):
    name: str
    project_code: str | None = None
    owner_id: int | None = None
    objective: str | None = None
    status: str = "Active"
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: float | None = None
    budget_currency: str | None = "CNY"
    notes: str | None = None


class ProjectOut(ProjectBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class CampaignBase(BaseModel):
    project_id: int | None = None
    product_id: int | None = None
    media_id: int
    owner_id: int | None = None
    collaboration_type: str | None = None
    stage: str = "Not Started"
    quotation_amount: float | None = None
    quotation_currency: str | None = None
    brief_sent: bool = False
    brief_sent_at: date | None = None
    sample_status: str = "Not Needed"
    expected_publish_date: date | None = None
    actual_publish_date: date | None = None
    notes: str | None = None
    execution_status: str = "待确认"
    next_action: str | None = None
    follow_up_date: date | None = None
    follow_up_priority: str = "普通"
    follow_up_done: bool = False


class CampaignOut(CampaignBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class DeliverableBase(BaseModel):
    campaign_id: int
    deliverable_type: str = "Other"
    title: str | None = None
    url: str | None = None
    published_at: date | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    impressions: int | None = None
    data_updated_at: datetime | None = None
    performance_notes: str | None = None


class DeliverableOut(DeliverableBase, ORMModel):
    id: int


class ShipmentItemBase(BaseModel):
    product_id: int | None = None
    product_name: str
    quantity: int = 1
    unit_cost: float | None = None


class CollaborationPatch(BaseModel):
    project_id: int | None = None
    media_id: int | None = None
    owner_id: int | None = None
    collaboration_type: str | None = None
    execution_status: str | None = None
    tracking_number: str | None = None
    expected_publish_date: date | None = None
    notes: str | None = None
    next_action: str | None = None
    follow_up_date: date | None = None
    follow_up_priority: str | None = None
    follow_up_done: bool | None = None


class CollaborationBulkPatch(BaseModel):
    ids: list[int]
    owner_id: int | None = None
    execution_status: str | None = None
    follow_up_date: date | None = None
    follow_up_priority: str | None = None


class ShipmentBase(BaseModel):
    campaign_id: int
    shipping_address_id: int | None = None
    recipient_address: str | None = None
    oa_pi_number: str | None = None
    tracking_number: str | None = None
    carrier: str | None = None
    status: str = "待发货"
    shipped_at: date | None = None
    delivered_at: date | None = None
    notes: str | None = None
    items: list[ShipmentItemBase] = []


class ProjectShipmentBase(BaseModel):
    media_id: int
    campaign_id: int | None = None
    shipping_address_id: int | None = None
    owner_id: int | None = None
    recipient_address: str | None = None
    oa_pi_number: str | None = None
    tracking_number: str | None = None
    carrier: str | None = None
    status: str = "待发货"
    shipped_at: date | None = None
    delivered_at: date | None = None
    notes: str | None = None
    items: list[ShipmentItemBase] = []


class ShipmentOut(ShipmentBase, ORMModel):
    id: int
    created_at: datetime


class CostItemBase(BaseModel):
    campaign_id: int
    cost_type: str
    planned_amount: float | None = None
    actual_amount: float | None = None
    currency: str = "CNY"
    payment_status: str = "未付款"
    reference_note: str | None = None


class CostItemOut(CostItemBase, ORMModel):
    id: int
    created_at: datetime


class ActivityBase(BaseModel):
    campaign_id: int
    activity_type: str = "备注"
    content: str


class ActivityOut(ActivityBase, ORMModel):
    id: int
    user_id: int | None = None
    created_at: datetime


class ListResponse(BaseModel):
    items: list[Any]
    total: int


class DashboardFilters(BaseModel):
    product_model: str | None = None
    country: str | None = None
    platform_type: str | None = None
    stage: str | None = None
    sample_status: str | None = None
    owner_id: int | None = None
    has_deliverable: bool | None = None
    date_from: date | None = None
    date_to: date | None = None
