"""Test setup.

Tests never touch the development database. A separate database,
picnic_permit_test, is created for the test run and migrated with Alembic,
and every test runs inside a transaction that is rolled back at the end.
"""

import os

TEST_DATABASE = "picnic_permit_test"
os.environ["POSTGRES_DB"] = TEST_DATABASE
os.environ["CAPTCHA_ENABLED"] = "true"
os.environ["ENVIRONMENT"] = "development"
os.environ["UPLOAD_DIR"] = "/tmp/pp-test-uploads"
os.environ["PUBLIC_BASE_URL"] = "https://picnic.example.test"

from collections.abc import Callable, Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core import security  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import District, DtoOffice, PoliceStation, Role, User  # noqa: E402
from app.services import captcha, masters, users  # noqa: E402
from app.services.users import OfficeLink  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
PASSWORD = "Picnic2026pass"


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> Iterator[None]:
    admin_engine = create_engine(
        get_settings().database_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))

    # Building the schema with the real migrations tests the migrations too.
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    yield
    engine.dispose()
    with admin_engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)'))
    admin_engine.dispose()


@pytest.fixture
def db() -> Iterator[Session]:
    """A session whose work, commits included, is undone after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        autoflush=False,
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        try:
            yield db
        except Exception:
            # As in the real app: a failed request leaves nothing half-saved.
            db.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"X-Requested-With": "fetch"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def anonymous(client: TestClient, db: Session) -> Iterator[TestClient]:
    """A second browser with no login cookie, on the same database session."""
    with TestClient(app, headers={"X-Requested-With": "fetch"}) as other:
        yield other


class Masters:
    def __init__(self, db: Session) -> None:
        self.tinsukia = masters.create_district(
            db, None, code=1022, name="Tinsukia", short_name="tinsukia"
        )
        self.cachar = masters.create_district(
            db, None, code=1004, name="Cachar", short_name="cachar"
        )
        self.goalpara = masters.create_district(
            db, None, code=1009, name="Goalpara", short_name="goalpara"
        )
        self.margherita = masters.create_police_station(
            db, None, name="Margherita PS", district_id=self.tinsukia.id
        )
        self.digboi = masters.create_police_station(
            db, None, name="Digboi PS", district_id=self.tinsukia.id
        )
        self.silchar = masters.create_police_station(
            db, None, name="Silchar PS", district_id=self.cachar.id
        )
        self.lakhipur = masters.create_police_station(
            db, None, name="Lakhipur PS", district_id=self.goalpara.id
        )
        self.dto_tinsukia = masters.create_dto_office(
            db,
            None,
            code="DTO-1022",
            name="District Transport Office, Tinsukia",
            district_id=self.tinsukia.id,
        )
        self.dto_cachar = masters.create_dto_office(
            db,
            None,
            code="DTO-1004",
            name="District Transport Office, Cachar",
            district_id=self.cachar.id,
        )
        db.commit()


@pytest.fixture
def m(db: Session) -> Masters:
    return Masters(db)


MakeUser = Callable[..., User]


@pytest.fixture
def make_user(db: Session) -> MakeUser:
    """Create an account with a known password that does not need changing."""

    def _make(
        role: Role,
        *,
        district: District | None = None,
        police_station: PoliceStation | None = None,
        dto_office: DtoOffice | None = None,
        must_change_password: bool = False,
        password: str | None = PASSWORD,
    ) -> User:
        user, _generated = users.create_user(
            db,
            None,
            role=role,
            link=OfficeLink(
                district=district, police_station=police_station, dto_office=dto_office
            ),
        )
        user.password_hash = security.hash_password(password) if password else None
        user.must_change_password = must_change_password
        db.commit()
        return user

    return _make


Login = Callable[..., object]


@pytest.fixture
def login(db: Session) -> Login:
    """Log a test client in, answering a fresh captcha."""

    def _login(test_client: TestClient, user_id: str, password: str = PASSWORD):
        captcha_id, answer, _image = captcha.create(db)
        db.commit()
        return test_client.post(
            "/api/auth/login",
            json={
                "user_id": user_id,
                "password": password,
                "captcha_id": captcha_id,
                "captcha_answer": answer,
            },
        )

    return _login


@pytest.fixture
def admin(make_user: MakeUser) -> User:
    return make_user(Role.STATE_ADMIN)


@pytest.fixture
def admin_client(client: TestClient, admin: User, login: Login) -> TestClient:
    assert login(client, admin.user_id).status_code == 200
    return client
