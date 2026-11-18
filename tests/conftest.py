import os

os.environ["DATABASE_URL"] = "sqlite:///./test_waypoint.db"

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


def pytest_configure():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def api():
    return TestClient(app)
