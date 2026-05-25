"""
agent_run_id — generate, thread, and propagate run IDs through agent loops.

Gives every agent run a stable ID you can attach to messages, logs,
tool calls, and traces so the whole session is traceable end-to-end.
Zero dependencies (stdlib: uuid, time, contextvars).
"""

from __future__ import annotations

import contextvars
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Core dataclass
# ---------------------------------------------------------------------------

@dataclass
class RunId:
    """
    A stable identifier for a single agent run.

    Attributes:
        id: Full UUID string (with optional prefix).
        prefix: Prefix used when building the ID.
        created_at: Unix timestamp when this RunId was created.
    """

    id: str
    prefix: str = "run"
    created_at: float = field(default_factory=time.time)

    @property
    def short(self) -> str:
        """First 8 hex characters after the prefix, for display."""
        raw = self.id
        if self.prefix and raw.startswith(self.prefix + "_"):
            raw = raw[len(self.prefix) + 1:]
        return raw[:8]

    def __str__(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return f"RunId({self.id!r})"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_run_id(prefix: str = "run") -> str:
    """
    Generate a new unique run ID string.

    Format: ``<prefix>_<uuid4_hex>``

    Args:
        prefix: String prepended to the UUID (default ``"run"``).
                Set to ``""`` for a bare UUID.

    Returns:
        Run ID string, e.g. ``"run_4f3a..."``
    """
    uid = uuid.uuid4().hex
    if prefix:
        return f"{prefix}_{uid}"
    return uid


def make_run_id(prefix: str = "run") -> RunId:
    """
    Create a new :class:`RunId` instance.

    Args:
        prefix: Prefix for the ID string.

    Returns:
        :class:`RunId`
    """
    return RunId(id=generate_run_id(prefix), prefix=prefix)


# ---------------------------------------------------------------------------
# Tagging helpers
# ---------------------------------------------------------------------------

_TAG_KEY = "_run_id"


def tag_message(message: dict[str, Any], run_id: RunId | str) -> dict[str, Any]:
    """
    Return a copy of *message* with the run ID injected.

    The run ID is stored under ``"_run_id"`` (not sent to the API;
    strip before sending with :func:`strip_tag`).

    Args:
        message: A message dict.
        run_id: :class:`RunId` or string.

    Returns:
        New dict with ``_run_id`` key added.
    """
    tagged = dict(message)
    tagged[_TAG_KEY] = str(run_id)
    return tagged


def tag_messages(
    messages: list[dict[str, Any]],
    run_id: RunId | str,
) -> list[dict[str, Any]]:
    """
    Return a new list with run ID injected into every message.

    Args:
        messages: List of message dicts.
        run_id: :class:`RunId` or string.

    Returns:
        New list of tagged dicts.
    """
    return [tag_message(m, run_id) for m in messages]


def strip_tag(message: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of *message* with the ``_run_id`` key removed.

    Use this before sending to the API.

    Args:
        message: A possibly-tagged message dict.

    Returns:
        New dict without ``_run_id``.
    """
    return {k: v for k, v in message.items() if k != _TAG_KEY}


def strip_tags(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Return a new list with ``_run_id`` stripped from every message.

    Args:
        messages: List of message dicts.

    Returns:
        New list without ``_run_id`` keys.
    """
    return [strip_tag(m) for m in messages]


def extract_run_id(message: dict[str, Any]) -> str | None:
    """
    Extract the run ID from a tagged message.

    Args:
        message: A possibly-tagged message dict.

    Returns:
        Run ID string, or ``None`` if not present.
    """
    return message.get(_TAG_KEY)


# ---------------------------------------------------------------------------
# Context variable (propagate across function calls)
# ---------------------------------------------------------------------------

_current_run_id: contextvars.ContextVar[RunId | None] = contextvars.ContextVar(
    "agent_run_id", default=None
)


def set_current_run_id(run_id: RunId | str) -> None:
    """
    Set the current run ID in the context.

    Args:
        run_id: :class:`RunId` or string. If a string is given, it is
                wrapped in a :class:`RunId`.
    """
    if isinstance(run_id, str):
        run_id = RunId(id=run_id)
    _current_run_id.set(run_id)


def get_current_run_id() -> RunId | None:
    """
    Get the current run ID from the context.

    Returns:
        :class:`RunId` or ``None`` if not set.
    """
    return _current_run_id.get()


def require_run_id() -> RunId:
    """
    Get the current run ID, raising if not set.

    Returns:
        :class:`RunId`

    Raises:
        RuntimeError: If no run ID is set in the current context.
    """
    rid = _current_run_id.get()
    if rid is None:
        raise RuntimeError(
            "No run ID is set in the current context. "
            "Call set_current_run_id() or use RunContext first."
        )
    return rid


def clear_run_id() -> None:
    """Clear the current run ID from the context."""
    _current_run_id.set(None)


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class RunContext:
    """
    Context manager that sets (and restores) the current run ID.

    Usage::

        with RunContext() as ctx:
            rid = ctx.run_id   # auto-generated
            messages = tag_messages(messages, rid)

        # Or supply an existing ID:
        with RunContext(run_id="run_abc123") as ctx:
            ...
    """

    def __init__(
        self,
        run_id: RunId | str | None = None,
        *,
        prefix: str = "run",
    ) -> None:
        if run_id is None:
            self.run_id = make_run_id(prefix)
        elif isinstance(run_id, str):
            self.run_id = RunId(id=run_id, prefix=prefix)
        else:
            self.run_id = run_id
        self._token: contextvars.Token[RunId | None] | None = None

    def __enter__(self) -> RunContext:
        self._token = _current_run_id.set(self.run_id)
        return self

    def __exit__(self, *_: Any) -> None:
        if self._token is not None:
            _current_run_id.reset(self._token)


# ---------------------------------------------------------------------------
# Annotation helper for logs / traces
# ---------------------------------------------------------------------------

def annotate(
    data: dict[str, Any],
    run_id: RunId | str | None = None,
    *,
    key: str = "run_id",
) -> dict[str, Any]:
    """
    Return a copy of *data* annotated with the run ID.

    If *run_id* is ``None``, uses the current context run ID.

    Args:
        data: Dict to annotate (log entry, trace event, etc.).
        run_id: Override run ID, or ``None`` to use context.
        key: Key to inject (default ``"run_id"``).

    Returns:
        New dict with run ID added.
    """
    if run_id is None:
        rid = get_current_run_id()
    else:
        rid = run_id
    result = dict(data)
    if rid is not None:
        result[key] = str(rid)
    return result
