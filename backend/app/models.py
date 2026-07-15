from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="Viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    campaigns = relationship("Campaign", back_populates="owner")


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    country: Mapped[str | None] = mapped_column(String(120), index=True)
    region: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    platform_type: Mapped[str | None] = mapped_column(String(120), index=True)
    website_url: Mapped[str | None] = mapped_column(Text)
    followers_or_traffic: Mapped[int | None] = mapped_column(Integer)
    media_tier: Mapped[str | None] = mapped_column(String(80))
    cooperation_status: Mapped[str | None] = mapped_column(String(120), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    contacts = relationship("Contact", back_populates="media", cascade="all, delete-orphan")
    shipping_addresses = relationship("ShippingAddress", back_populates="media", cascade="all, delete-orphan")
    campaigns = relationship("Campaign", back_populates="media")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(160))
    role: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(120))
    whatsapp: Mapped[str | None] = mapped_column(String(120))
    telegram: Mapped[str | None] = mapped_column(String(120))
    brief_email: Mapped[str | None] = mapped_column(String(255))
    press_release_email: Mapped[str | None] = mapped_column(String(255))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    media = relationship("Media", back_populates="contacts")
    shipping_addresses = relationship("ShippingAddress", back_populates="contact")


class ShippingAddress(Base):
    __tablename__ = "shipping_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id"), index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True, index=True)
    recipient_name: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    address_text: Mapped[str] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str | None] = mapped_column(String(120))
    tax_or_customs_number: Mapped[str | None] = mapped_column(String(255))
    shipping_notes: Mapped[str | None] = mapped_column(Text)
    source_text: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    media = relationship("Media", back_populates="shipping_addresses")
    contact = relationship("Contact", back_populates="shipping_addresses")
    shipments = relationship("Shipment", back_populates="shipping_address")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), index=True)
    product_line: Mapped[str | None] = mapped_column(String(120))
    platform: Mapped[str | None] = mapped_column(String(120))
    aliases: Mapped[str | None] = mapped_column(Text)
    launch_status: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)

    campaigns = relationship("Campaign", back_populates="product")
    project_links = relationship("ProjectProduct", back_populates="product", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    project_code: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    objective: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="Active", index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    budget_amount: Mapped[float | None] = mapped_column(Float)
    budget_currency: Mapped[str | None] = mapped_column(String(20), default="CNY")
    notes: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    owner = relationship("User")
    campaigns = relationship("Campaign", back_populates="project")
    product_links = relationship("ProjectProduct", back_populates="project", cascade="all, delete-orphan")


class ProjectProduct(Base):
    __tablename__ = "project_products"
    __table_args__ = (UniqueConstraint("project_id", "product_id", name="uq_project_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    project = relationship("Project", back_populates="product_links")
    product = relationship("Product", back_populates="project_links")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True, index=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id"), index=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    collaboration_type: Mapped[str | None] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(40), default="Not Started", index=True)
    quotation_amount: Mapped[float | None] = mapped_column(Float)
    quotation_currency: Mapped[str | None] = mapped_column(String(20))
    brief_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    brief_sent_at: Mapped[date | None] = mapped_column(Date)
    sample_status: Mapped[str] = mapped_column(String(40), default="Not Needed", index=True)
    expected_publish_date: Mapped[date | None] = mapped_column(Date)
    actual_publish_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    execution_status: Mapped[str] = mapped_column(String(40), default="待确认", index=True)
    next_action: Mapped[str | None] = mapped_column(String(255))
    follow_up_date: Mapped[date | None] = mapped_column(Date, index=True)
    follow_up_priority: Mapped[str] = mapped_column(String(20), default="普通", index=True)
    follow_up_done: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_historical: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    product = relationship("Product", back_populates="campaigns")
    project = relationship("Project", back_populates="campaigns")
    media = relationship("Media", back_populates="campaigns")
    owner = relationship("User", back_populates="campaigns")
    deliverables = relationship("Deliverable", back_populates="campaign", cascade="all, delete-orphan")
    shipments = relationship("Shipment", back_populates="campaign", cascade="all, delete-orphan")
    cost_items = relationship("CostItem", back_populates="campaign", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="campaign", cascade="all, delete-orphan")


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    shipping_address_id: Mapped[int | None] = mapped_column(ForeignKey("shipping_addresses.id"), nullable=True, index=True)
    recipient_address: Mapped[str | None] = mapped_column(Text)
    oa_pi_number: Mapped[str | None] = mapped_column(String(160), index=True)
    tracking_number: Mapped[str | None] = mapped_column(String(255), index=True)
    carrier: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="待发货", index=True)
    shipped_at: Mapped[date | None] = mapped_column(Date)
    delivered_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    campaign = relationship("Campaign", back_populates="shipments")
    shipping_address = relationship("ShippingAddress", back_populates="shipments")
    items = relationship("ShipmentItem", back_populates="shipment", cascade="all, delete-orphan")


class ShipmentItem(Base):
    __tablename__ = "shipment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_cost: Mapped[float | None] = mapped_column(Float)

    shipment = relationship("Shipment", back_populates="items")
    product = relationship("Product")


class CostItem(Base):
    __tablename__ = "cost_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    cost_type: Mapped[str] = mapped_column(String(60), index=True)
    planned_amount: Mapped[float | None] = mapped_column(Float)
    actual_amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(20), default="CNY")
    payment_status: Mapped[str] = mapped_column(String(40), default="未付款", index=True)
    reference_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    campaign = relationship("Campaign", back_populates="cost_items")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    activity_type: Mapped[str] = mapped_column(String(60), default="备注")
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    campaign = relationship("Campaign", back_populates="activities")
    user = relationship("User")


class Deliverable(Base):
    __tablename__ = "deliverables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), index=True)
    deliverable_type: Mapped[str] = mapped_column(String(80), default="Other", index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[date | None] = mapped_column(Date, index=True)
    views: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer)
    data_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    performance_notes: Mapped[str | None] = mapped_column(Text)

    campaign = relationship("Campaign", back_populates="deliverables")
