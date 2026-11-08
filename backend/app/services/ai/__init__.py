"""DeepSeek client (OpenAI-compatible, private server) and generation (AGENTS.md §6)."""
import asyncio
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar

import httpx
from pydantic import Field, ValidationError

from app.config import settings
from app.models import AiAnswer, AiSummary, CamelModel
from app.services.ai.prompts import (NO_CRS_ANSWER, PolicyContext, ask_messages, build_context, build_sources,
                                     is_record_question, newest_per_chamber, record_key_points, record_summary_text,
                                     summary_messages, vote_point)
from app.services.http import make_client

MAX_OUTPUT_TOKENS = 2000  # includes the model's reasoning
MAX_KEY_POINTS = 5
ATTEMPTS = 2  # one retry when the output can't be used
RECORD_ONLY = "official record (no AI)"
_MONTH_DAY = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
                        r"\s+\d{1,2}\b")
_LIST_MARKER = re.compile(r"^\s*\d{1,2}[.)]\s+", re.MULTILINE)

T = TypeVar("T")

_gate = asyncio.Semaphore(settings.deepseek_max_concurrent)


class AiUnavailable(Exception):
    """The AI server is unset, down, busy or too slow. The message is safe to show users."""


class AiBadOutput(Exception):
    """The model answered, but not in a usable form."""


class _SummaryDraft(CamelModel):
    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.deepseek_api_key}"} if settings.deepseek_api_key else {}


def _base_url() -> str:
    return settings.deepseek_base_url.rstrip("/")


def strip_thinking(text: str) -> str:
    """Remove a reasoning model's <think> block, including one that was cut off or only half present."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.split("<think>")[0]
    return text.split("</think>")[-1].strip()


def _json_block(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise AiBadOutput("no JSON object in the response")
    return text[start:end + 1]


async def _complete(messages: list[dict], json_mode: bool) -> str:
    payload: dict = {"model": settings.deepseek_model, "messages": messages, "temperature": 0.2,
                     "max_tokens": MAX_OUTPUT_TOKENS, "stream": False}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        async with make_client(timeout=settings.deepseek_timeout_seconds) as http:
            res = await http.post(f"{_base_url()}/chat/completions", json=payload, headers=_headers())
    except (httpx.HTTPError, httpx.InvalidURL) as e:
        raise AiUnavailable("The AI service can't be reached right now.") from e
    if res.status_code >= 400:
        raise AiUnavailable("The AI service returned an error.")
    try:
        # Only `content` is read, so a separate reasoning field is never used.
        content = res.json()["choices"][0]["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise AiBadOutput("malformed response") from e
    return strip_thinking(content)


async def _generate(messages: list[dict], parse: Callable[[str], T], json_mode: bool) -> T:
    """Queue for the GPU, then generate and parse, retrying once. One time budget covers all of it."""
    if not (settings.deepseek_base_url and settings.deepseek_model):
        raise AiUnavailable("The AI service is not configured.")
    try:
        async with asyncio.timeout(settings.deepseek_timeout_seconds), _gate:
            for attempt in range(ATTEMPTS):
                try:
                    return parse(await _complete(messages, json_mode))
                except AiBadOutput:
                    if attempt == ATTEMPTS - 1:
                        raise
    except TimeoutError as e:
        raise AiUnavailable("The AI service is busy or too slow right now. Try again shortly.") from e
    except AiBadOutput as e:
        raise AiUnavailable("The AI service couldn't produce a usable answer. Try again.") from e
    raise AssertionError("unreachable")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text)}


def _check_grounded(output: str, context: str) -> None:
    """Reject output with a number or month-and-day missing from the context block.

    Only the context counts: a number in the user's question or the task text isn't evidence.
    """
    output = _LIST_MARKER.sub("", output)
    if _numbers(output) - _numbers(context):
        raise AiBadOutput("output contains a number that is not in the context")
    if set(_MONTH_DAY.findall(output)) - set(_MONTH_DAY.findall(context)):
        raise AiBadOutput("output contains a date that is not in the context")


async def generate_summary(ctx: PolicyContext) -> AiSummary:
    messages = summary_messages(ctx)
    context = build_context(ctx, vote_details=False)

    def parse(text: str) -> _SummaryDraft:
        try:
            draft = _SummaryDraft.model_validate_json(_json_block(text))
        except ValidationError as e:
            raise AiBadOutput("response did not match the summary shape") from e
        _check_grounded("\n".join([draft.summary, *draft.key_points]), context)
        return draft

    draft = await _generate(messages, parse, json_mode=True)
    points = [p.strip() for p in draft.key_points if p.strip()][:MAX_KEY_POINTS]
    points += [vote_point(v) for v in newest_per_chamber(ctx.votes)]
    return AiSummary(policy_id=ctx.policy.policy_id, model=settings.deepseek_model,
                     generated_at=datetime.now(timezone.utc), summary=draft.summary.strip(),
                     key_points=points, sources=build_sources(ctx))


def record_summary(ctx: PolicyContext) -> AiSummary:
    """The official record only, for items with no CRS text. Needs no model, so it works when the AI is down."""
    return AiSummary(policy_id=ctx.policy.policy_id, model=RECORD_ONLY, generated_at=datetime.now(timezone.utc),
                     summary=record_summary_text(ctx.policy), key_points=record_key_points(ctx.policy, ctx.votes),
                     sources=build_sources(ctx))


async def answer_question(ctx: PolicyContext, question: str) -> AiAnswer:
    if not ctx.policy.crs_summary and not is_record_question(question):
        # Decided in code, because with only a title the model invents what a bill does.
        return AiAnswer(policy_id=ctx.policy.policy_id, model=RECORD_ONLY, generated_at=datetime.now(timezone.utc),
                        question=question, answer=NO_CRS_ANSWER)

    messages = ask_messages(ctx, question)
    context = build_context(ctx)

    def parse(text: str) -> str:
        if not text:
            raise AiBadOutput("empty answer")
        _check_grounded(text, context)
        return text

    answer = await _generate(messages, parse, json_mode=False)
    return AiAnswer(policy_id=ctx.policy.policy_id, model=settings.deepseek_model,
                    generated_at=datetime.now(timezone.utc), question=question, answer=answer,
                    sources=build_sources(ctx))


async def is_up() -> bool:
    if not settings.deepseek_base_url:
        return False
    try:
        async with make_client(timeout=3.0) as http:
            res = await http.get(f"{_base_url()}/models", headers=_headers())
    except (httpx.HTTPError, httpx.InvalidURL):
        return False
    return res.status_code == 200
