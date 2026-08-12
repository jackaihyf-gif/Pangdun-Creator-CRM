import os
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DB_PATH = Path(tempfile.gettempdir()) / f"pangdun-crm-test-{uuid.uuid4().hex}.sqlite3"
os.environ["PANGDUN_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

from backend.app.auth import create_access_token  # noqa: E402
from backend.app.database import Base, SessionLocal, engine  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.models import Campaign, Media, Project, User  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_collaboration():
    with SessionLocal() as db:
        user = User(
            email="admin@example.test",
            password_hash="not-used-in-api-tests",
            name="Test Admin",
            role="Admin",
            is_active=True,
        )
        media = Media(name="Test Creator", country="US", platform_type="YouTube")
        project = Project(name="Test Launch", project_code="TEST-001", status="Active")
        db.add_all([user, media, project])
        db.flush()
        campaign = Campaign(
            project_id=project.id,
            media_id=media.id,
            owner_id=user.id,
            stage="Not Started",
            sample_status="Not Needed",
            execution_status="待确认",
            next_action="确认合作意向与报价",
            follow_up_priority="普通",
            follow_up_done=False,
            is_historical=False,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        token = create_access_token(user)
        return {
            "campaign_id": campaign.id,
            "project_id": project.id,
            "headers": {"Authorization": f"Bearer {token}"},
        }


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    TEST_DB_PATH.unlink(missing_ok=True)
