# LLM Eval API

A FastAPI-based AI evaluation platform that accepts test requests, calls an LLM, evaluates the response, stores results, and returns structured output.

## Stack

- **FastAPI** — API layer
- **SQLAlchemy** — ORM
- **SQLite** — database
- **LiteLLM** — multi-provider LLM abstraction (Gemini, OpenAI, Groq, Ollama, and more)
- **Docker** — containerisation

## Project Structure

```
app/
├── main.py               # App entry point, startup, error handling
├── config.py             # Environment config
├── routes/tests.py       # API endpoints
├── schemas/test.py       # Request/response models
├── services/
│   ├── llm_service.py    # LLM abstraction (mock or real)
│   ├── test_runner.py    # Evaluation logic
│   └── orchestrator.py  # Coordinates LLM → evaluation → DB
├── models/test_result.py # Database model
└── db/                   # Session, base, init
tests/
├── conftest.py           # Shared fixtures (in-memory DB, mocked LLM)
├── test_api.py           # API integration tests
└── test_test_runner.py   # Unit tests for evaluation logic
```

## Setup

### 1. Configure environment

```bash
cp .env.example .env
```

`.env.example` contains ready-to-use examples for all supported configurations: cloud models (Gemini, OpenAI, Groq), local models via Ollama, multiple cloud judges, and mock mode. Uncomment the block that matches your setup.

### 2. Run with Docker

```bash
docker compose up                       # cloud models or mock
docker compose --profile local-llm up  # include Ollama for local models
```

The API is available at `http://localhost:8000`.
Interactive docs (Swagger) at `http://localhost:8000/docs`.

## API

### `POST /run-test`

Submit a test. Returns `202 Accepted` immediately with `result: "pending"`. The LLM call and evaluation run in the background — poll `GET /tests/{id}` for the final result.

**Request**
```json
{
  "input": "Explain quantum computing simply",
  "test_type": "keyword"
}
```

`test_type` options: `"length"`, `"keyword"`, `"llm_judge"`

**Response**
```json
{
  "id": 1,
  "result": "pending"
}
```

---

### `GET /tests/{id}`

Poll for a result. `result` transitions from `"pending"` → `"passed"` or `"failed"`.

**Response**
```json
{
  "id": 1,
  "input": "Explain quantum computing simply",
  "output": "Quantum computing uses qubits...",
  "test_type": "llm_judge",
  "result": "passed",
  "score": 0.88,
  "judge_scores": [
    {"model": "gemini/gemini-2.5-flash-lite", "score": 0.9, "reason": "Clear and accurate explanation."},
    {"model": "openai/gpt-4o-mini", "score": 0.85, "reason": "Good coverage, slightly verbose."}
  ],
  "judge_agreement": 0.95,
  "judge_errors": [],
  "execution_time": 1.24,
  "llm_source": "ollama/tinyllama",
  "timestamp": "2026-04-10T20:49:08.125983"
}
```

`judge_scores`, `judge_agreement`, and `judge_errors` are populated only for `llm_judge` tests. `judge_errors` lists any judges that failed with their error message — a non-empty list means the score is based on fewer judges than configured. Non-judge tests return `[]`, `null`, and `[]` respectively.

---

### `GET /tests`

List past results, most recent first. Supports pagination via query params:

| Param | Type | Default | Max | Description |
|---|---|---|---|---|
| `limit` | int | 20 | 100 | Number of results to return |
| `offset` | int | 0 | — | Number of results to skip |

Example: `GET /tests?limit=10&offset=20`

---

### `GET /health`

```json
{ "status": "ok" }
```

## Test Types

| Type | Description | Pass condition |
|---|---|---|
| `length` | Checks word count of the LLM response | Between 10 and 200 words |
| `keyword` | Checks if key terms from the input appear in the output | ≥ 50% of significant input words found in output |
| `llm_judge` | One or more LLM judges score the response on relevance, accuracy, and clarity | Average score ≥ 0.7 |

## LLM Behaviour

| `LLM_MODEL` set | Behaviour |
|---|---|
| No | Mock response — `llm_source: "mock"` |
| Yes (cloud) | Real LLM call via LiteLLM — `llm_source: "<provider>/<model>"` |
| Yes (Ollama) | Local model call — requires `docker compose --profile local-llm up` |

API keys are set using standard provider env vars (`GEMINI_API_KEY`, `OPENAI_API_KEY`, etc.) and picked up by LiteLLM automatically. No key is needed for local Ollama models.

## LLM-as-a-Judge

The `llm_judge` test type implements an LLM-based evaluation pattern where one or more judge models score a response for relevance, accuracy, and clarity:

- Configure multiple judges via `LLM_JUDGE_MODELS` (e.g. Gemini + GPT-4o-mini + Claude)
- Each judge scores independently and in parallel
- The final `score` is the average of all judge scores; individual scores are returned in `judge_scores`
- `judge_agreement` measures score consistency: `1 - (max_score - min_score)`. A value of `1.0` means all judges gave the same score; `0.0` means maximum spread. Single-judge tests always return `1.0`
- Using judges from different providers avoids self-enhancement bias (a model rating its own output)

## Further Reading

The following papers are relevant to the evaluation techniques used in this project.

1. Zheng, L., Chiang, W.-L., Sheng, Y., et al. (2023). [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685). *arXiv*.  
   Evaluates LLMs as judges via pairwise comparison and benchmarks them against human preferences.

2. Liu, Y., Xu, Q., Zhang, X., et al. (2024). [G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment](https://arxiv.org/abs/2303.16634). *EMNLP 2024 Findings*.  
   Uses GPT-4 with rubric-based evaluation to better align automated scores with human judgments.

3. Madaan, A., Tandon, N., Gupta, P., et al. (2023). [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651). *NeurIPS 2023*.  
   Introduces a generate → critique → refine loop using LLM self-feedback.

4. Bai, Y., Kadavath, S., Kundu, S., et al. (2022). [Constitutional AI: Harmlessness from AI Feedback](https://arxiv.org/abs/2212.08073). *arXiv*.  
   Uses rule-based critique and revision to guide model outputs.

5. Gu, J., et al. (2024). [LLM-as-a-Judge: A Survey](https://arxiv.org/abs/2411.15594). *arXiv*.  
   Surveys evaluation methods and biases in LLM-based judging.

6. Wang, P., et al. (2023). [Large Language Models are not Fair Evaluators](https://arxiv.org/abs/2305.17926). *ACL 2023 Findings*.  
   Highlights positional bias and inconsistency in single-judge setups.

## Running Tests

```bash
pip install -r requirements.txt
pytest
```

Tests use an in-memory SQLite database and mock all LLM calls — no API keys or running containers needed.

## Docker Commands

```bash
docker compose up                       # start (dev mode, hot reload)
docker compose up -d                    # start in background
docker compose --profile local-llm up  # start with Ollama (required for local models)
docker compose down                     # stop
docker compose down -v                  # stop and wipe database
docker compose logs -f api              # stream logs
```

> **Local models via Ollama:** The `local-llm` profile is opt-in so that `docker compose up` stays fast for users using cloud models or the mock. On first run, Ollama pulls the configured model (~600 MB for TinyLlama, ~4 GB for Mistral), which is cached in a named volume for subsequent starts.
