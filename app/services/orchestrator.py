import logging
import time

from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import SessionLocal
from app.models.test_result import TestResult
from app.schemas.test import RunTestRequest
from app.services import llm_service
from app.services import test_runner as runner
from app.services.test_runner import TestOutcome

logger = logging.getLogger(__name__)


def run_test(db: Session, request: RunTestRequest) -> TestResult:
    """Creates a pending record and returns immediately."""
    if request.test_type == "llm_judge" and not settings.get_judge_configs():
        raise ValueError(
            "llm_judge requires at least one judge to be configured. "
            "Set LLM_JUDGE_MODELS in your environment."
        )

    record = TestResult(
        input=request.input,
        test_type=request.test_type,
    )
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except Exception as e:
        db.rollback()
        raise ValueError("Failed to create test record.") from e
    return record


async def execute_test(test_id: int, request: RunTestRequest) -> None:
    """Runs LLM + evaluation in the background. Uses its own DB session."""
    db = SessionLocal()
    try:
        record = db.get(TestResult, test_id)
        if not record:
            return

        start = time.perf_counter()
        try:
            llm_result = await llm_service.get_llm_response(request.input)
            record.output = llm_result.content
            record.llm_source = llm_result.source

            if request.test_type == "llm_judge":
                outcome, judge_scores, judge_agreement, judge_errors = await _run_llm_judge(request.input, llm_result.content)
                record.judge_scores = judge_scores
                record.judge_agreement = judge_agreement
                record.judge_errors = judge_errors or None
            else:
                outcome = runner.run_test(request.test_type, llm_result.content, request.input)

            record.result = outcome.status
            record.score = outcome.score
            record.execution_time = round(time.perf_counter() - start, 4)
        except ValueError as e:
            logger.error("Test execution failed for id=%s: %s", test_id, e)
            record.result = "failed"
            record.output = record.output or str(e)
            record.execution_time = round(time.perf_counter() - start, 4)

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Background task crashed for test_id=%s", test_id)
        try:
            record = db.get(TestResult, test_id)
            if record and record.result == "pending":
                record.result = "failed"
                db.commit()
        except Exception:
            logger.exception("Could not mark test_id=%s as failed after crash", test_id)
    finally:
        db.close()


async def _run_llm_judge(input_prompt: str, output: str) -> tuple[TestOutcome, list[dict], float | None, list[dict]]:
    judge_results, judge_errors = await llm_service.get_all_judge_evaluations(input_prompt, output)

    if not judge_results:
        return TestOutcome(status="failed", score=0.0), [], None, judge_errors

    scores = [j.score for j in judge_results]
    avg_score = round(sum(scores) / len(scores), 2)
    agreement = round(1 - (max(scores) - min(scores)), 2) if len(scores) > 1 else 1.0
    status = "passed" if avg_score >= 0.7 else "failed"

    judge_scores = [
        {"model": j.model, "score": j.score, "reason": j.reason}
        for j in judge_results
    ]
    return TestOutcome(status=status, score=avg_score), judge_scores, agreement, judge_errors


def get_all_tests(db: Session, limit: int = 20, offset: int = 0) -> list[TestResult]:
    return db.query(TestResult).order_by(TestResult.timestamp.desc()).offset(offset).limit(limit).all()


def get_test_by_id(db: Session, test_id: int) -> TestResult | None:
    return db.get(TestResult, test_id)
