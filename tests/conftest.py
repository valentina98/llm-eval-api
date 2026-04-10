import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.services.llm_service import LLMResult, JudgeResult


# StaticPool shares one in-memory SQLite connection across all sessions,
# so the route session and the background task's SessionLocal see the same data.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Redirect the background task's own SessionLocal to the test engine.
    with patch("app.services.orchestrator.SessionLocal", TestingSessionLocal):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def mock_llm():
    """Patches get_llm_response to return a fixed mock response."""
    mock = AsyncMock(return_value=LLMResult(
        content="This is a mock LLM response for testing purposes only.",
        source="mock",
    ))
    with patch("app.services.llm_service.get_llm_response", mock):
        yield mock


@pytest.fixture()
def mock_judges():
    """Patches get_all_judge_evaluations to return two fixed judge scores."""
    results = [
        JudgeResult(model="mock-judge-a", score=0.9, reason="Excellent."),
        JudgeResult(model="mock-judge-b", score=0.8, reason="Good."),
    ]
    mock = AsyncMock(return_value=(results, []))
    with patch("app.services.llm_service.get_all_judge_evaluations", mock):
        yield mock
