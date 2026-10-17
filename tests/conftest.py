import pytest
import database
from app import app as flask_app


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every test at a fresh, empty SQLite file so tests are independent."""
    monkeypatch.setattr(database, "DATABASE", str(tmp_path / "test.db"))
    database.init_db()


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c
