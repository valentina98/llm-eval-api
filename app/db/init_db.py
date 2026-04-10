from app.db.base import Base
from app.db.session import engine
import app.models.test_result  # noqa: F401 — ensures model is registered


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
