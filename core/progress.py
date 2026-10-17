"""
Progress events of an analysis run, for a caller that shows progress live.

The web UI turns them into server-sent events; the CLI passes no callback and
follows the log instead. One event is one stage, or one item of a stage (an
evaluator, a data step), changing status. Codes (stage, status, verdict) are
for programs; label and text are the words a person reads.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass

# "not_computed": a step that could not run on this data (the DCF without revenue or a share
# count), which is a data limitation, not a failure.
STATUSES = ("started", "done", "failed", "skipped", "not_computed")


@dataclass(frozen=True)
class ProgressEvent:
    stage: str                          # e.g. "input_check", "lens", "synthesis"
    status: str                         # one of STATUSES
    key: str | None = None              # the item within the stage, e.g. a lens key
    label: str | None = None            # its name for people
    text: str | None = None             # what happened, in words
    verdict: str | None = None          # verdict code, for styling only
    verdict_text: str | None = None     # the verdict in words
    confidence_text: str | None = None
    cost_usd: float | None = None       # estimated cost of the call (of the whole run for
                                        # the caller's final "run" event); None if unknown

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"Unknown progress status {self.status!r}; expected one of {STATUSES}")

    def to_dict(self) -> dict:
        return asdict(self)


ProgressCallback = Callable[[ProgressEvent], None]
