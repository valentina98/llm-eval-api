import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.db.init_db import init_db
from app.routes.tests import router as tests_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initialising database")
    init_db()
    _configure_llm()
    yield
    logger.info("Shutting down")


def _configure_llm() -> None:
    from app.services import llm_service
    llm_service.configure()


app = FastAPI(
    title="LLM Eval API",
    description="An LLM evaluation platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(tests_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok"}
