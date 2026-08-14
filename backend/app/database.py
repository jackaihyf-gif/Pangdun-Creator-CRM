import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "kol_crm.db"

SQLALCHEMY_DATABASE_URL = os.getenv("PANGDUN_DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def apply_compat_migrations() -> None:
    """Keep the LAN MVP self-updating without asking users to run migrations."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "media" in tables:
            columns = {column["name"] for column in inspector.get_columns("media")}
            if "audience_metric_type" not in columns:
                connection.execute(text("ALTER TABLE media ADD COLUMN audience_metric_type VARCHAR(40)"))
            if "audience_metric_unit" not in columns:
                connection.execute(text("ALTER TABLE media ADD COLUMN audience_metric_unit VARCHAR(20)"))
            if "profile_links" not in columns:
                connection.execute(text("ALTER TABLE media ADD COLUMN profile_links JSON DEFAULT '[]'"))
            if "metric_source" not in columns:
                connection.execute(text("ALTER TABLE media ADD COLUMN metric_source VARCHAR(255)"))
            if "metric_verified_at" not in columns:
                connection.execute(text("ALTER TABLE media ADD COLUMN metric_verified_at DATE"))
            if "country_code" not in columns:
                connection.execute(text("ALTER TABLE media ADD COLUMN country_code VARCHAR(2)"))
            if "verification_status" not in columns:
                connection.execute(text("ALTER TABLE media ADD COLUMN verification_status VARCHAR(40) DEFAULT '待核验'"))
            additions = {
                "data_source": "VARCHAR(255)",
                "data_capture_method": "VARCHAR(40)",
                "data_confidence": "FLOAT",
                "last_verified_at": "DATE",
                "review_snoozed_until": "DATE",
                "youtube_channel_id": "VARCHAR(120)",
                "youtube_uploads_playlist_id": "VARCHAR(120)",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE media ADD COLUMN {name} {definition}"))
        if "contacts" in tables:
            columns = {column["name"] for column in inspector.get_columns("contacts")}
            additions = {
                "data_source": "VARCHAR(255)",
                "data_capture_method": "VARCHAR(40)",
                "data_confidence": "FLOAT",
                "verified_at": "DATE",
                "created_at": "DATETIME",
                "updated_at": "DATETIME",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE contacts ADD COLUMN {name} {definition}"))
            connection.execute(text("UPDATE contacts SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP), updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"))
        if "campaigns" in tables:
            columns = {column["name"] for column in inspector.get_columns("campaigns")}
            additions = {
                "project_id": "INTEGER",
                "execution_status": "VARCHAR(40) DEFAULT '待确认'",
                "next_action": "VARCHAR(255)",
                "follow_up_date": "DATE",
                "follow_up_priority": "VARCHAR(20) DEFAULT '普通'",
                "follow_up_done": "BOOLEAN DEFAULT 0",
                "is_historical": "BOOLEAN DEFAULT 0",
                "execution_status_changed_at": "DATETIME",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE campaigns ADD COLUMN {name} {definition}"))
                    if name == "is_historical":
                        connection.execute(text("UPDATE campaigns SET is_historical = 1 WHERE project_id IS NULL"))
                    if name == "execution_status_changed_at":
                        connection.execute(text("UPDATE campaigns SET execution_status_changed_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))
            if "archived_at" not in columns:
                connection.execute(text("ALTER TABLE campaigns ADD COLUMN archived_at DATETIME"))
            connection.execute(text("UPDATE campaigns SET execution_status = '已暂停' WHERE execution_status = '已暂停/取消'"))
            if "campaign_stage_events" in tables:
                connection.execute(text("""
                    INSERT INTO campaign_stage_events (campaign_id, user_id, from_status, to_status, action, reason, created_at)
                    SELECT campaigns.id, NULL, NULL, COALESCE(campaigns.execution_status, '待确认'), 'migration', '阶段治理上线时建立基线',
                           COALESCE(campaigns.execution_status_changed_at, campaigns.updated_at, campaigns.created_at, CURRENT_TIMESTAMP)
                    FROM campaigns
                    WHERE NOT EXISTS (
                        SELECT 1 FROM campaign_stage_events WHERE campaign_stage_events.campaign_id = campaigns.id
                    )
                """))
        if "projects" in tables:
            columns = {column["name"] for column in inspector.get_columns("projects")}
            additions = {
                "is_archived": "BOOLEAN DEFAULT 0",
                "archived_at": "DATETIME",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE projects ADD COLUMN {name} {definition}"))
        if "deliverables" in tables:
            columns = {column["name"] for column in inspector.get_columns("deliverables")}
            if "impressions" not in columns:
                connection.execute(text("ALTER TABLE deliverables ADD COLUMN impressions INTEGER"))
            additions = {
                "platform_content_id": "VARCHAR(120)",
                "platform_channel_id": "VARCHAR(120)",
                "matched_tag": "VARCHAR(120)",
                "match_method": "VARCHAR(80)",
                "platform_published_at": "DATETIME",
                "first_detected_at": "DATETIME",
                "monitoring_status": "VARCHAR(40)",
                "monitoring_completed_at": "DATETIME",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE deliverables ADD COLUMN {name} {definition}"))
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_deliverables_platform_content_id ON deliverables (platform_content_id) WHERE platform_content_id IS NOT NULL"))
        if "shipments" in tables:
            columns = {column["name"] for column in inspector.get_columns("shipments")}
            if "shipping_address_id" not in columns:
                connection.execute(text("ALTER TABLE shipments ADD COLUMN shipping_address_id INTEGER"))
