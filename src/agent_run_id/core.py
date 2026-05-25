"""Generate, format, and thread run IDs through LLM agent pipelines.

Run IDs help correlate logs, spans, and events across an agent turn.
:class:`RunId` handles generation and formatting; :class:`RunIdStore`
is a lightweight in-process registry that maps session keys to run IDs.

Example::

    from agent_run_id import RunId, RunIdStore

    # Generate a run ID
    run_id = RunId.generate()                # "run_7f4a2b1c"
    sub_id = run_id.child("step_1")          # "run_7f4a2b1c.step_1"

    # Thread it through a store
    store = RunIdStore()
    store.set("session:abc", run_id)

    print(store.get("session:abc"))          # RunId("run_7f4a2b1c")
    print(store.require("session:abc").full) # "run_7f4a2b1c"
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


class RunIdNotSetError(KeyError):
    """Raised by :meth:`RunIdStore.require` when the key has no run ID."""


@dataclass(frozen=True)
class RunId:
    """An immutable run ID with optional hierarchy support.

    Attributes:
        value:    The core ID string (without prefix or parent).
        prefix:   Short prefix for human readability (default ``"run"``).
        parent:   Parent :class:`RunId` when this is a child/sub-run.
    """

    value: str
    prefix: str = "run"
    parent: RunId | None = field(default=None, compare=False)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def generate(cls, prefix: str = "run") -> RunId:
        """Generate a new random run ID.

        Uses the first 8 hex characters of a UUID4 for brevity.

        Args:
            prefix: Short prefix.  Defaults to ``"run"``.

        Returns:
            A new :class:`RunId`.
        """
        short = uuid.uuid4().hex[:8]
        return cls(value=short, prefix=prefix)

    @classmethod
    def from_string(cls, s: str, prefix: str = "run") -> RunId:
        """Construct a :class:`RunId` from a pre-existing string.

        The string is used as-is for :attr:`value`.

        Args:
            s:      The raw ID value.
            prefix: Prefix to attach.

        Returns:
            A :class:`RunId` wrapping *s*.
        """
        return cls(value=s, prefix=prefix)

    # ------------------------------------------------------------------
    # Hierarchy
    # ------------------------------------------------------------------

    def child(self, label: str) -> RunId:
        """Create a child run ID that references this one.

        The child's :attr:`full` string is ``{parent.full}.{label}``.

        Args:
            label: A short label for the child step.

        Returns:
            A new :class:`RunId` with ``parent=self``.
        """
        return RunId(value=label, prefix=self.prefix, parent=self)

    # ------------------------------------------------------------------
    # String representations
    # ------------------------------------------------------------------

    @property
    def full(self) -> str:
        """Full dotted-path representation including parent chain.

        Examples:
            ``"run_7f4a2b1c"`` for a root ID.
            ``"run_7f4a2b1c.step_1"`` for a child.
            ``"run_7f4a2b1c.step_1.attempt_2"`` for a grandchild.
        """
        if self.parent is None:
            return f"{self.prefix}_{self.value}"
        return f"{self.parent.full}.{self.value}"

    @property
    def short(self) -> str:
        """Just the local segment (no parent prefix)."""
        if self.parent is None:
            return f"{self.prefix}_{self.value}"
        return self.value

    @property
    def root(self) -> RunId:
        """Walk up the parent chain and return the root run ID."""
        if self.parent is None:
            return self
        return self.parent.root

    @property
    def depth(self) -> int:
        """Nesting depth (0 for root, 1 for child, 2 for grandchild, …)."""
        if self.parent is None:
            return 0
        return self.parent.depth + 1

    # ------------------------------------------------------------------
    # Extras
    # ------------------------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (useful for logging)."""
        return {
            "run_id": self.full,
            "root_id": self.root.full,
            "depth": self.depth,
        }

    def __str__(self) -> str:
        return self.full

    def __repr__(self) -> str:
        return f"RunId({self.full!r})"


class RunIdStore:
    """A lightweight registry mapping arbitrary keys to :class:`RunId` values.

    Useful for correlating run IDs with sessions, requests, or threads.
    """

    def __init__(self) -> None:
        self._store: dict[str, RunId] = {}

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def set(self, key: str, run_id: RunId) -> RunIdStore:
        """Store *run_id* under *key*.

        Args:
            key:    Arbitrary string key.
            run_id: :class:`RunId` to associate.

        Returns:
            ``self`` for chaining.
        """
        self._store[key] = run_id
        return self

    def set_new(self, key: str, prefix: str = "run") -> RunId:
        """Generate a new run ID, store it, and return it.

        Args:
            key:    Arbitrary string key.
            prefix: Prefix for the generated ID.

        Returns:
            The newly generated :class:`RunId`.
        """
        run_id = RunId.generate(prefix=prefix)
        self._store[key] = run_id
        return run_id

    def delete(self, key: str) -> RunIdStore:
        """Remove the run ID for *key* (no-op if absent).

        Returns:
            ``self`` for chaining.
        """
        self._store.pop(key, None)
        return self

    def clear(self) -> RunIdStore:
        """Remove all entries.

        Returns:
            ``self`` for chaining.
        """
        self._store.clear()
        return self

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, key: str, default: RunId | None = None) -> RunId | None:
        """Return the :class:`RunId` for *key*, or *default* if absent."""
        return self._store.get(key, default)

    def require(self, key: str) -> RunId:
        """Return the :class:`RunId` for *key* or raise if absent.

        Raises:
            RunIdNotSetError: If *key* has no associated run ID.
        """
        if key not in self._store:
            raise RunIdNotSetError(key)
        return self._store[key]

    def has(self, key: str) -> bool:
        """Return ``True`` if *key* has an associated run ID."""
        return key in self._store

    def keys(self) -> list[str]:
        """Return a sorted list of all stored keys."""
        return sorted(self._store.keys())

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        """Number of stored run IDs."""
        return len(self._store)

    @property
    def is_empty(self) -> bool:
        """``True`` if no run IDs are stored."""
        return len(self._store) == 0

    def __repr__(self) -> str:
        return f"RunIdStore(count={self.count})"

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: object) -> bool:
        return key in self._store
