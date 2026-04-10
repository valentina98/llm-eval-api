from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.test import RunTestRequest, RunTestResponse, TestResultResponse
from app.db.session import get_db
from app import services

router = APIRouter(tags=["tests"])


@router.post("/run-test", response_model=RunTestResponse, status_code=202)
def run_test(
    request: RunTestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submit a test against the LLM.

    Returns **202 Accepted** immediately with `result: "pending"`.
    The LLM call and evaluation run in the background.
    Poll `GET /tests/{id}` until `result` is `"passed"` or `"failed"`.
    """
    try:
        record = services.run_test(db, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    background_tasks.add_task(services.execute_test, record.id, request)
    return record


@router.get("/tests", response_model=list[TestResultResponse])
def list_tests(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Return test results, most recent first. Paginate with `limit` and `offset`."""
    return services.get_all_tests(db, limit=limit, offset=offset)


@router.get("/tests/{test_id}", response_model=TestResultResponse)
def get_test(test_id: int, db: Session = Depends(get_db)):
    """Return a single test result by ID. Use this to poll for a pending result."""
    result = services.get_test_by_id(db, test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    return result
