"""
Configuration: API key, model, prices and request settings.

Everything a run may vary comes from .env, so an eval can compare variants of
one code version without editing it.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY_ENV_VAR = "ANTHROPIC_API_KEY"
API_KEY_PREFIX = "sk-ant-"
ANTHROPIC_API_KEY = os.getenv(API_KEY_ENV_VAR)


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


# Fail fast: a missing key would otherwise surface as an error from every call.
if not ANTHROPIC_API_KEY or not ANTHROPIC_API_KEY.startswith(API_KEY_PREFIX):
    raise ConfigurationError(
        f"{API_KEY_ENV_VAR} is missing or invalid "
        f"(expected a key starting with '{API_KEY_PREFIX}').\n"
        "Copy .env.example to .env in the project root and set your API key there."
    )

# Model for every analysis call. ANALYSIS_MODEL in .env overrides it.
# Sonnet 5.5: cheaper than Sonnet 4.6 (2 / 10 vs 3 / 15 USD per MTok), cache reads
# at 0.05x, a 512-token cache minimum. Its default effort is high: measure output
# tokens on the first real run.
DEFAULT_MODEL = "claude-sonnet-5-5"
MODEL = os.getenv("ANALYSIS_MODEL", "").strip() or DEFAULT_MODEL

# USD per million tokens: (input, output). Used only for the cost estimate after
# a run. Checked 2026-10-15 on the Anthropic pricing page; check again before
# relying on the estimates.
MODEL_PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

# Models priced by prompt length: (threshold in tokens, input, output) for a request
# whose prompt is longer than the threshold. The prompt length counts all input
# tokens including cache reads and writes, and the whole request is then billed at
# the higher prices, cache reads and writes included (pricing page, checked 2026-10-15).
LONG_PROMPT_PRICING_PER_MTOK: dict[str, tuple[int, float, float]] = {
    "claude-haiku-5-5": (100_000, 0.50, 2.50),
}

# Prompt caching prices, as multipliers of the model's input price (prompt caching
# docs, checked 2026-10-15). A 5-minute cache write costs 1.25x; a read costs 0.1x,
# except on the models listed in CACHE_READ_MULTIPLIER_BY_MODEL.
CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10
CACHE_READ_MULTIPLIER_BY_MODEL: dict[str, float] = {
    "claude-opus-5-5": 0.05,
    "claude-sonnet-5-5": 0.05,
}
# A prefix shorter than the model's minimum is silently not cached (no error):
# 512 tokens for Sonnet 5.5, Opus 5.5 and Haiku 5.5; 1,024 for Sonnet 4.6 and
# Sonnet 5; 4,096 for Haiku 4.5 (prompt caching docs, checked 2026-10-15).
# structured_call warns when a request asked for caching and nothing was cached.

# Prompt caching of the shared prefix (rules + shared context). Pays off when two
# or more calls share the prefix within 5 minutes. PROMPT_CACHING=off in .env
# disables it, e.g. to measure its effect.
PROMPT_CACHING = os.getenv("PROMPT_CACHING", "on").strip().lower() not in ("0", "false", "no", "off")

# Thinking before answering: "off" or "adaptive" (the model decides how much).
# "off" sends no thinking parameter. Sonnet 4.6 then does not think, but Sonnet 5.5,
# Opus 5.5 and Haiku 5.5 think adaptively anyway (their thinking cannot be disabled
# that way; ANALYSIS_EFFORT is the control there).
# Thinking tokens are billed as output and count against MAX_TOKENS.
THINKING_MODES = ("off", "adaptive")
THINKING = os.getenv("THINKING", "").strip().lower() or "off"
if THINKING not in THINKING_MODES:
    raise ConfigurationError(f"THINKING must be one of {', '.join(THINKING_MODES)}, got {THINKING!r}")

# Effort: how much the model thinks and writes. Unset = the model's default.
# A different effort between calls breaks a shared cache, so keep it per run.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
ANALYSIS_EFFORT = os.getenv("ANALYSIS_EFFORT", "").strip().lower() or None
if ANALYSIS_EFFORT and ANALYSIS_EFFORT not in EFFORT_LEVELS:
    raise ConfigurationError(
        f"ANALYSIS_EFFORT must be one of {', '.join(EFFORT_LEVELS)}, got {ANALYSIS_EFFORT!r}"
    )

# Per-call output limit, thinking included; a truncated response is treated as an error.
# Sonnet 5.5 at its default effort used 12,227 output tokens for one Forensic answer
# (2026-10-15). Without streaming the SDK refuses requests that may run over 10 minutes,
# which it estimates as max_tokens above 21,333 (anthropic 1.7.0, _base_client.py).
MAX_TOKENS = 20000

# Web search, for the perspectives that need live facts. Billed per search on top
# of tokens (10 USD per 1,000 searches when this was written; check the price).
WEB_SEARCH_PRICE = 0.01

# Translated copies of a finished report (translate/): a cheap model at low effort,
# a stricter retry at medium effort for a section whose answer was rejected (as in
# Startup Autopsy, where Haiku 5.5 at low effort translated a report for about
# 0.02 USD). The English report stays the source of truth.
TRANSLATION_MODEL = "claude-haiku-5-5"
TRANSLATION_EFFORT = "low"
TRANSLATION_RETRY_EFFORT = "medium"
