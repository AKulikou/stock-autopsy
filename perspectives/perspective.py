"""
A perspective: one independent analytical angle (a lens in Startup Autopsy, an
evaluator in Stock Autopsy), defined as data, and the call that runs it.

Prompt layout, chosen for prompt caching:

    system block 1 (cached): shared standards + shared context    <- identical for all
    system block 2:          role and focus of this perspective   <- differs
    user message:            the questions of this perspective     <- differs

Anything that differs between perspectives comes after the cache breakpoint, so
every perspective after the first reads the shared part from the cache, provided the
requests also share the output schema: the API renders the schema as a system prompt
of its own ahead of block 1, so a schema per perspective is a prefix per perspective.
With SHARED_OUTPUT_SCHEMA the evaluators send one envelope schema (AnalystOutput) and
each fills its own field.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from config import ANALYSIS_EFFORT, MAX_TOKENS, MODEL, PROMPT_CACHING, SHARED_OUTPUT_SCHEMA, THINKING
from core.claude_client import get_client
from core.structured_call import billed_usage, request_structured
from evaluators.schemas import AnalystOutput


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


def perspective_user(perspective: Perspective, material: str | None = None) -> str:
    """The questions, then any material for this call only (results an earlier step computed)."""
    questions = "\n".join(f"{n}. {q}" for n, q in enumerate(perspective.questions, start=1))
    text = f"Analyze the shared context through your perspective. Address these questions:\n\n{questions}"
    return f"{text}\n\n{material}" if material else text


def envelope_field(output_format: type[BaseModel]) -> str | None:
    """The AnalystOutput field that carries this schema, or None for a schema outside it."""
    for name, field in AnalystOutput.model_fields.items():
        if output_format in getattr(field.annotation, "__args__", ()):
            return name
    return None


def envelope_request(
    output_format: type[BaseModel], validate: Callable[[BaseModel], list[str]], user: str
) -> tuple[type[BaseModel], Callable[[BaseModel], list[str]], str, Callable[[BaseModel], BaseModel]]:
    """
    The shared schema in place of `output_format`: the same request for every
    evaluator up to the user message, which names the field to fill. Returns the
    schema, a validator of the envelope, the user text and the unwrapping function.
    """
    field = envelope_field(output_format)
    others = [name for name in AnalystOutput.model_fields if name != field]

    def validate_envelope(envelope: AnalystOutput) -> list[str]:
        answer = getattr(envelope, field)
        filled = [name for name in others if getattr(envelope, name) is not None]
        problems = [f"fill only the field {field}; set {', '.join(filled)} to null"] if filled else []
        if answer is None:
            return [*problems, f"the field {field} is null; your answer belongs there"]
        return problems + validate(answer)

    note = f"Put your answer in the output field {field} and set every other field to null."
    return AnalystOutput, validate_envelope, f"{user}\n\n{note}", lambda envelope: getattr(envelope, field)


def evaluate(
    perspective: Perspective,
    prefix: str,
    output_format: type[BaseModel],
    validate: Callable[[BaseModel], list[str]],
    material: str | None = None,
) -> dict:
    """
    Run one perspective and return a result dict: "status": "success" with the
    structured fields, or "status": "error" with the message. Never raises.
    `material` goes after the questions, outside the cached prefix.
    """
    started = time.monotonic()
    base = {"key": perspective.key, "label": perspective.name, "model": MODEL}
    user = perspective_user(perspective, material)
    unwrap = None
    if SHARED_OUTPUT_SCHEMA and envelope_field(output_format):
        output_format, validate, user, unwrap = envelope_request(output_format, validate, user)
    try:
        response = request_structured(
            get_client(),
            label=perspective.name,
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=perspective_system(perspective),
            user=user,
            output_format=output_format,
            validate=validate,
            cached_prefix=prefix if PROMPT_CACHING else None,
            thinking=THINKING == "adaptive",
            effort=ANALYSIS_EFFORT,
        )
        return {
            **base,
            "status": "success",
            **(unwrap(response.result) if unwrap else response.result).model_dump(mode="json"),
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
