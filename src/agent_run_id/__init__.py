"""agent-run-id - generate, thread, and propagate unique run IDs through agent sessions.

Correlation IDs for logging, tracing, and audit across tool calls and sub-agents.
Supports parent/child relationships and HTTP header propagation. Zero runtime deps.

    from agent_run_id import RunContext, with_run_id, inject_headers, extract_headers

    # Start a new top-level run
    ctx = RunContext.new()

    # Propagate to a child (sub-agent, tool call, etc.)
    child = ctx.child()

    # Thread-local current run
    with with_run_id(ctx):
        from agent_run_id import get_current
        assert get_current() == ctx

    # HTTP header propagation
    headers = inject_headers(ctx, {})
    # => {"X-Run-Id": "...", "X-Parent-Run-Id": "..." (if parent set)}
    received = extract_headers(headers)  # reconstructs RunContext from headers
"""

import threading
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

__version__ = "0.1.0"

__all__ = [
    "RunContext",
    "set_current",
    "get_current",
    "clear_current",
    "with_run_id",
    "inject_headers",
    "extract_headers",
    "__version__",
]


@dataclass(frozen=True)
class RunContext:
    """Immutable container for a single agent run's identity.

    Attributes:
        run_id:     uuid4 hex string (no dashes) uniquely identifying this run.
        parent_id:  run_id of the parent run, or None for a top-level run.
        created_at: ISO 8601 UTC timestamp when this context was created.
    """

    run_id: str
    parent_id: str | None = None
    created_at: str = ""

    @classmethod
    def new(cls, parent_id: str | None = None) -> "RunContext":
        """Create a new RunContext with a fresh uuid4 run_id and current UTC timestamp.

        Args:
            parent_id: Optional run_id of the parent run. Defaults to None.

        Returns:
            A new RunContext instance.
        """
        return cls(
            run_id=uuid.uuid4().hex,
            parent_id=parent_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def child(self, name: str | None = None) -> "RunContext":
        """Create a child RunContext whose parent_id is this run's run_id.

        Args:
            name: Reserved for future use; currently ignored.

        Returns:
            A new RunContext with parent_id set to self.run_id.
        """
        # name is intentionally unused — reserved for future labeling of child spans.
        _ = name
        return RunContext.new(parent_id=self.run_id)

    def to_dict(self) -> dict:
        """Serialize to a plain dict.

        The parent_id key is omitted entirely when None.

        Returns:
            Dict with run_id and created_at always present; parent_id when set.
        """
        d: dict = {
            "run_id": self.run_id,
            "created_at": self.created_at,
        }
        if self.parent_id is not None:
            d["parent_id"] = self.parent_id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RunContext":
        """Reconstruct a RunContext from a dict produced by to_dict().

        Args:
            d: Dict with at least a "run_id" key.

        Returns:
            A RunContext instance.
        """
        return cls(
            run_id=d["run_id"],
            parent_id=d.get("parent_id"),
            created_at=d.get("created_at", ""),
        )


# Module-level thread-local storage for the current run context.
_local = threading.local()


def set_current(ctx: RunContext) -> None:
    """Set the current thread-local RunContext.

    Args:
        ctx: The RunContext to make current.
    """
    _local.ctx = ctx


def get_current() -> RunContext | None:
    """Return the current thread-local RunContext, or None if not set.

    Returns:
        The active RunContext, or None.
    """
    return getattr(_local, "ctx", None)


def clear_current() -> None:
    """Clear the current thread-local RunContext."""
    _local.ctx = None


@contextmanager
def with_run_id(ctx: RunContext) -> Generator[RunContext, None, None]:
    """Context manager that makes ctx the current RunContext for the duration of the block.

    Restores the previous RunContext (or None) on exit, enabling correct nesting.

    Args:
        ctx: The RunContext to activate.

    Yields:
        The supplied RunContext.
    """
    previous = get_current()
    set_current(ctx)
    try:
        yield ctx
    finally:
        # Restore to whatever was current before — handles nested with_run_id correctly.
        if previous is None:
            clear_current()
        else:
            set_current(previous)


# HTTP header names used for propagation.
_HEADER_RUN_ID = "X-Run-Id"
_HEADER_PARENT_RUN_ID = "X-Parent-Run-Id"


def inject_headers(ctx: RunContext, headers: dict) -> dict:
    """Return a new dict with X-Run-Id (and optionally X-Parent-Run-Id) added.

    Does not mutate the input dict.

    Args:
        ctx:     The RunContext whose IDs should be injected.
        headers: Existing headers dict to extend.

    Returns:
        A new dict containing all original headers plus the run-id headers.
    """
    result = dict(headers)
    result[_HEADER_RUN_ID] = ctx.run_id
    if ctx.parent_id is not None:
        result[_HEADER_PARENT_RUN_ID] = ctx.parent_id
    return result


def extract_headers(headers: dict) -> RunContext | None:
    """Reconstruct a RunContext from HTTP headers, using case-insensitive key lookup.

    Args:
        headers: Headers dict (any case for keys).

    Returns:
        A RunContext if X-Run-Id is present; None otherwise.
        created_at defaults to the current UTC time when not found in headers.
    """
    # Normalize all keys to lowercase for case-insensitive lookup.
    normalized = {k.lower(): v for k, v in headers.items()}

    run_id = normalized.get(_HEADER_RUN_ID.lower())
    if run_id is None:
        return None

    parent_id = normalized.get(_HEADER_PARENT_RUN_ID.lower())
    return RunContext(
        run_id=run_id,
        parent_id=parent_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
