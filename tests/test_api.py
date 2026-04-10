import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_service import LLMResult, JudgeResult


class TestHealth:
    def test_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestRunTest:
    def test_returns_202_with_pending(self, client, mock_llm):
        response = client.post("/run-test", json={"input": "Hello", "test_type": "length"})
        assert response.status_code == 202
        data = response.json()
        assert data["result"] == "pending"
        assert "id" in data

    def test_invalid_test_type_returns_422(self, client):
        response = client.post("/run-test", json={"input": "Hello", "test_type": "bad"})
        assert response.status_code == 422

    def test_empty_input_returns_422(self, client):
        response = client.post("/run-test", json={"input": "", "test_type": "length"})
        assert response.status_code == 422

    def test_input_too_long_returns_422(self, client):
        response = client.post("/run-test", json={"input": "x" * 2001, "test_type": "length"})
        assert response.status_code == 422

    def test_llm_judge_without_judges_returns_400(self, client):
        with patch("app.config.Settings.get_judge_configs", return_value=[]):
            response = client.post("/run-test", json={"input": "Hello", "test_type": "llm_judge"})
        assert response.status_code == 400
        assert "judge" in response.json()["detail"].lower()


class TestGetTest:
    def test_not_found_returns_404(self, client):
        response = client.get("/tests/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Test not found"

    def test_pending_record_returned_immediately(self, client, mock_llm):
        post = client.post("/run-test", json={"input": "Hello", "test_type": "length"})
        test_id = post.json()["id"]
        # BackgroundTasks run synchronously in TestClient
        response = client.get(f"/tests/{test_id}")
        assert response.status_code == 200
        assert response.json()["id"] == test_id

    def test_length_test_completes(self, client, mock_llm):
        post = client.post("/run-test", json={"input": "Explain recursion", "test_type": "length"})
        test_id = post.json()["id"]
        response = client.get(f"/tests/{test_id}")
        data = response.json()
        assert data["result"] in ("passed", "failed")
        assert data["llm_source"] == "mock"
        assert data["score"] is not None
        assert data["execution_time"] > 0

    def test_keyword_test_completes(self, client, mock_llm):
        post = client.post("/run-test", json={"input": "mock response", "test_type": "keyword"})
        test_id = post.json()["id"]
        response = client.get(f"/tests/{test_id}")
        data = response.json()
        assert data["result"] in ("passed", "failed")

    def test_llm_judge_test_completes(self, client, mock_llm, mock_judges):
        post = client.post("/run-test", json={"input": "What is AI?", "test_type": "llm_judge"})
        test_id = post.json()["id"]
        response = client.get(f"/tests/{test_id}")
        data = response.json()
        assert data["result"] in ("passed", "failed")
        assert len(data["judge_scores"]) == 2
        assert data["judge_agreement"] is not None
        assert data["judge_errors"] == []
        assert data["score"] == round((0.9 + 0.8) / 2, 2)

    def test_judge_errors_surfaced_on_partial_failure(self, client, mock_llm):
        results = [JudgeResult(model="mock-judge-a", score=0.9, reason="Good.")]
        errors = [{"model": "mock-judge-b", "error": "Model not found."}]
        mock = AsyncMock(return_value=(results, errors))
        with patch("app.services.llm_service.get_all_judge_evaluations", mock):
            post = client.post("/run-test", json={"input": "Hello", "test_type": "llm_judge"})
            test_id = post.json()["id"]
            response = client.get(f"/tests/{test_id}")
        data = response.json()
        assert len(data["judge_scores"]) == 1
        assert len(data["judge_errors"]) == 1
        assert data["judge_errors"][0]["model"] == "mock-judge-b"

    def test_all_judges_fail_surfaces_errors(self, client, mock_llm):
        errors = [
            {"model": "judge-a", "error": "Not found."},
            {"model": "judge-b", "error": "Auth failed."},
        ]
        mock = AsyncMock(return_value=([], errors))
        with patch("app.services.llm_service.get_all_judge_evaluations", mock):
            post = client.post("/run-test", json={"input": "Hello", "test_type": "llm_judge"})
            test_id = post.json()["id"]
            response = client.get(f"/tests/{test_id}")
        data = response.json()
        assert data["result"] == "failed"
        assert data["score"] == 0.0
        assert len(data["judge_errors"]) == 2
        assert data["judge_scores"] == []

    def test_non_judge_fields_are_empty_for_length_test(self, client, mock_llm):
        post = client.post("/run-test", json={"input": "Hello", "test_type": "length"})
        test_id = post.json()["id"]
        data = client.get(f"/tests/{test_id}").json()
        assert data["judge_scores"] == []
        assert data["judge_agreement"] is None
        assert data["judge_errors"] == []


class TestListTests:
    def test_returns_empty_list_initially(self, client):
        response = client.get("/tests")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_submitted_tests(self, client, mock_llm):
        client.post("/run-test", json={"input": "Hello", "test_type": "length"})
        client.post("/run-test", json={"input": "World", "test_type": "keyword"})
        response = client.get("/tests")
        assert len(response.json()) == 2

    def test_default_limit_is_20(self, client, mock_llm):
        for i in range(25):
            client.post("/run-test", json={"input": f"Question {i}", "test_type": "length"})
        response = client.get("/tests")
        assert len(response.json()) == 20

    def test_limit_param(self, client, mock_llm):
        for i in range(10):
            client.post("/run-test", json={"input": f"Question {i}", "test_type": "length"})
        response = client.get("/tests?limit=5")
        assert len(response.json()) == 5

    def test_offset_param(self, client, mock_llm):
        for i in range(10):
            client.post("/run-test", json={"input": f"Question {i}", "test_type": "length"})
        all_tests = client.get("/tests?limit=10").json()
        offset_tests = client.get("/tests?limit=10&offset=5").json()
        assert len(offset_tests) == 5
        assert offset_tests[0]["id"] == all_tests[5]["id"]

    def test_limit_above_100_returns_422(self, client):
        response = client.get("/tests?limit=101")
        assert response.status_code == 422

    def test_most_recent_first(self, client, mock_llm):
        client.post("/run-test", json={"input": "First", "test_type": "length"})
        client.post("/run-test", json={"input": "Second", "test_type": "length"})
        results = client.get("/tests").json()
        assert results[0]["input"] == "Second"
        assert results[1]["input"] == "First"
