"""
A perspective: one independent analytical angle (a lens in Startup Autopsy, an
evaluator in Stock Autopsy), defined as data, and the call that runs it.

Prompt layout, chosen for prompt caching:

    system block 1 (cached): shared standards + shared context    <- identical for all
    system block 2:          role and focus of this perspective   <- differs
    user message:            the questions of this perspective     <- differs

Anything that differs between perspectives comes after the cache breakpoint, so
every perspective after the first reads the shared part from the cache.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from config import ANALYSIS_EFFORT, MAX_TOKENS, MODEL, PROMPT_CACHING, THINKING
from core.claude_client import get_client
from core.structured_call import billed_usage, request_structured


@dataclass(frozen=True)
class Perspective:
    key: str  # stable identifier, used in config, file names and eval data
    name: str  # display name for reports
    role: str  # who the model acts as
    focus: str  # the single question this perspective answers
    questions: tuple[str, ...]


def shared_prefix(standards: str, context: str) -> str:
    """The part every perspective shares: standards first, then the context block."""
    return f"{standards.strip()}\n\n{context}"


def perspective_system(perspective: Perspective) -> str:
    return f"You are {perspective.role}.\n\nYour perspective: {perspective.focus}"


def perspective_user(perspective: Perspective) -> str:
    questions = "\n".join(f"{n}. {q}" for n, q in enumerate(perspective.questions, start=1))
    return f"Analyze the shared context through your perspective. Address these questions:\n\n{questions}"


def evaluate(
    perspective: Perspective,
    prefix: str,
    output_format: type[BaseModel],
    validate: Callable[[BaseModel], list[str]],
) -> dict:
    """
    Run one perspective and return a result dict: "status": "success" with the
    structured fields, or "status": "error" with the message. Never raises.
    """
    started = time.monotonic()
    base = {"key": perspective.key, "label": perspective.name, "model": MODEL}
    try:
        response = request_structured(
            get_client(),
            label=perspective.name,
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=perspective_system(perspective),
            user=perspective_user(perspective),
            output_format=output_format,
            validate=validate,
            cached_prefix=prefix if PROMPT_CACHING else None,
            thinking=THINKING == "adaptive",
            effort=ANALYSIS_EFFORT,
        )
        return {
            **base,
            "status": "success",
            **response.result.model_dump(mode="json"),
            **response.usage.as_dict(),
            "duration_s": time.monotonic() - started,
        }
    except Exception as e:
        return {
            **base,
            "status": "error",
            "error": f"{type(e).__name__}: {e}",
            "duration_s": time.monotonic() - started,
            **billed_usage(e),
        }
