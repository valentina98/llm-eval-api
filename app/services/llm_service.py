import asyncio
import json
import logging
import re
from dataclasses import dataclass

import litellm

from app.config import settings

logger = logging.getLogger(__name__)


_JUDGE_PROMPT = """You are an AI evaluator. Score the following LLM response to the given question.

Question: {input}

Response: {output}

Rate the response from 0.0 to 1.0 where:
- 1.0 = perfectly answers the question, accurate and clear
- 0.5 = partially answers the question
- 0.0 = completely wrong or irrelevant

Respond with ONLY a JSON object in this exact format:
{{"score": 0.85, "reason": "one sentence explanation"}}"""


@dataclass
class LLMResult:
    content: str
    source: str   # "mock" | "<provider>/<model>"


@dataclass
class JudgeResult:
    model: str
    score: float
    reason: str


def configure() -> None:
    """Log LLM configuration at startup. Called once from main.py."""
    if settings.llm_model:
        source = f"{settings.llm_model} (local via {settings.llm_api_base})" if settings.llm_api_base else settings.llm_model
        logger.info("LLM configured: %s", source)
    else:
        logger.info("LLM_MODEL not set — mock LLM will be used")

    judge_configs = settings.get_judge_configs()
    if judge_configs:
        logger.info("Judge LLMs configured: %s", ", ".join(judge_configs))


async def get_llm_response(prompt: str) -> LLMResult:
    if settings.llm_model:
        return await _call_llm(prompt, settings.llm_model, api_base=settings.llm_api_base)
    return await _mock_llm_response(prompt)


async def get_all_judge_evaluations(
    input_prompt: str, output: str
) -> tuple[list[JudgeResult], list[dict]]:
    """Run all configured judges in parallel. Returns (results, errors)."""
    configs = settings.get_judge_configs()
    if not configs:
        return [await _mock_judge_evaluation()], []

    prompt = _JUDGE_PROMPT.format(input=input_prompt, output=output)
    tasks = [_judge_with_model(prompt, model) for model in configs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    judge_results = []
    judge_errors = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("Judge %s failed: %s", configs[i], result)
            judge_errors.append({"model": configs[i], "error": str(result)})
        else:
            judge_results.append(result)

    return judge_results, judge_errors


async def _judge_with_model(prompt: str, model: str) -> JudgeResult:
    result = await _call_llm(prompt, model)
    parsed = _parse_judge_response(result.content)
    return JudgeResult(model=model, score=parsed.score, reason=parsed.reason)


async def _mock_llm_response(prompt: str) -> LLMResult:
    logger.info("Using mock LLM (LLM_MODEL not set)")
    await asyncio.sleep(0.5)
    content = (
        "[MOCK] This is a simulated response. "
        "It covers the topic with a clear explanation suitable for a general audience."
    )
    return LLMResult(content=content, source="mock")


async def _mock_judge_evaluation() -> JudgeResult:
    logger.info("Using mock judge (no judges configured)")
    await asyncio.sleep(0.3)
    return JudgeResult(model="mock", score=0.5, reason="Mock evaluation — no judges configured.")


async def _call_llm(prompt: str, model: str, api_base: str | None = None) -> LLMResult:
    try:
        kwargs: dict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if api_base:
            kwargs["api_base"] = api_base
        response = await litellm.acompletion(**kwargs)
    except litellm.RateLimitError as e:
        logger.error("Rate limit [%s]: %s", model, e)
        msg = (
            "LLM quota exceeded. Check your billing and plan limits."
            if "quota" in str(e).lower()
            else "LLM rate limit exceeded. Try again later."
        )
        raise ValueError(msg) from e
    except litellm.AuthenticationError as e:
        logger.error("Auth error [%s]: %s", model, e)
        raise ValueError("LLM authentication failed. Check your API key.") from e
    except litellm.BadRequestError as e:
        logger.error("Bad request [%s]: %s", model, e)
        raise ValueError("LLM rejected the request. Check LLM_MODEL format.") from e
    except litellm.NotFoundError as e:
        logger.error("Model not found [%s]: %s", model, e)
        raise ValueError(f"Model '{model}' not found. Check LLM_MODEL.") from e
    except litellm.APIConnectionError as e:
        logger.error("Connection error [%s]: %s", model, e)
        hint = f" Is the server running at {api_base}?" if api_base else ""
        raise ValueError(f"Could not connect to LLM '{model}'.{hint}") from e
    except litellm.ServiceUnavailableError as e:
        logger.error("Service unavailable [%s]: %s", model, e)
        raise ValueError("LLM service unavailable. Try again later.") from e
    except litellm.Timeout as e:
        logger.error("Timeout [%s]: %s", model, e)
        raise ValueError("LLM request timed out. Try again later.") from e
    content = response.choices[0].message.content
    return LLMResult(content=content, source=model)


def _parse_judge_response(text: str) -> JudgeResult:
    text = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    try:
        data = json.loads(text)
        score = max(0.0, min(1.0, float(data["score"])))
        return JudgeResult(model="", score=round(score, 2), reason=data.get("reason", ""))
    except Exception:
        match = re.search(r"\b(0\.\d+|1\.0|0|1)\b", text)
        score = float(match.group()) if match else 0.5
        return JudgeResult(model="", score=round(score, 2), reason="")
