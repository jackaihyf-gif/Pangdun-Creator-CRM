from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "kol_crm.db"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
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
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE campaigns ADD COLUMN {name} {definition}"))
                    if name == "is_historical":
                        connection.execute(text("UPDATE campaigns SET is_historical = 1 WHERE project_id IS NULL"))
            if "archived_at" not in columns:
                connection.execute(text("ALTER TABLE campaigns ADD COLUMN archived_at DATETIME"))
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
        if "shipments" in tables:
            columns = {column["name"] for column in inspector.get_columns("shipments")}
            if "shipping_address_id" not in columns:
                connection.execute(text("ALTER TABLE shipments ADD COLUMN shipping_address_id INTEGER"))
