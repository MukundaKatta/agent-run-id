"""Tests for agent_run_id."""

import dataclasses
import threading

import pytest

from agent_run_id import (
    RunContext,
    clear_current,
    extract_headers,
    get_current,
    inject_headers,
    set_current,
    with_run_id,
)

# ---------------------------------------------------------------------------
# RunContext.new()
# ---------------------------------------------------------------------------


def test_new_creates_unique_run_id_each_call():
    a = RunContext.new()
    b = RunContext.new()
    assert a.run_id != b.run_id


def test_new_run_id_is_32_char_hex():
    ctx = RunContext.new()
    assert len(ctx.run_id) == 32
    int(ctx.run_id, 16)  # raises ValueError if not valid hex


def test_new_created_at_is_iso8601_string():
    from datetime import datetime

    ctx = RunContext.new()
    # datetime.fromisoformat raises if the string is invalid
    parsed = datetime.fromisoformat(ctx.created_at)
    assert parsed.tzinfo is not None  # must be timezone-aware


def test_new_with_parent_id():
    ctx = RunContext.new(parent_id="abc123")
    assert ctx.parent_id == "abc123"


def test_new_without_parent_id_is_none():
    ctx = RunContext.new()
    assert ctx.parent_id is None


# ---------------------------------------------------------------------------
# RunContext.child()
# ---------------------------------------------------------------------------


def test_child_parent_id_equals_self_run_id():
    parent = RunContext.new()
    child = parent.child()
    assert child.parent_id == parent.run_id


def test_child_has_different_run_id_from_parent():
    parent = RunContext.new()
    child = parent.child()
    assert child.run_id != parent.run_id


def test_child_has_its_own_created_at():
    parent = RunContext.new()
    child = parent.child()
    # Both must be valid ISO strings; they may differ by a tiny amount
    from datetime import datetime

    datetime.fromisoformat(child.created_at)
    assert isinstance(child.created_at, str) and len(child.created_at) > 0


def test_child_name_arg_is_ignored():
    parent = RunContext.new()
    child_named = parent.child(name="step-1")
    assert child_named.parent_id == parent.run_id


# ---------------------------------------------------------------------------
# to_dict()
# ---------------------------------------------------------------------------


def test_to_dict_includes_run_id_and_created_at():
    ctx = RunContext.new()
    d = ctx.to_dict()
    assert "run_id" in d
    assert "created_at" in d
    assert d["run_id"] == ctx.run_id


def test_to_dict_omits_parent_id_key_when_none():
    ctx = RunContext.new()
    d = ctx.to_dict()
    assert "parent_id" not in d


def test_to_dict_includes_parent_id_when_set():
    ctx = RunContext.new(parent_id="p123")
    d = ctx.to_dict()
    assert d["parent_id"] == "p123"


# ---------------------------------------------------------------------------
# from_dict()
# ---------------------------------------------------------------------------


def test_from_dict_round_trips():
    ctx = RunContext.new(parent_id="r999")
    d = ctx.to_dict()
    restored = RunContext.from_dict(d)
    assert restored.run_id == ctx.run_id
    assert restored.parent_id == ctx.parent_id
    assert restored.created_at == ctx.created_at


def test_from_dict_parent_id_optional():
    ctx = RunContext.new()
    d = ctx.to_dict()
    assert "parent_id" not in d
    restored = RunContext.from_dict(d)
    assert restored.parent_id is None


# ---------------------------------------------------------------------------
# Immutability (frozen dataclass)
# ---------------------------------------------------------------------------


def test_run_context_is_frozen():
    ctx = RunContext.new()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        ctx.run_id = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Thread-local set/get/clear
# ---------------------------------------------------------------------------


def test_get_current_returns_none_before_set():
    clear_current()
    assert get_current() is None


def test_set_and_get_current_round_trip():
    ctx = RunContext.new()
    set_current(ctx)
    assert get_current() is ctx
    clear_current()


def test_clear_current_clears_it():
    ctx = RunContext.new()
    set_current(ctx)
    clear_current()
    assert get_current() is None


def test_thread_local_is_isolated_across_threads():
    """Each thread should see its own current context."""
    ctx_main = RunContext.new()
    set_current(ctx_main)

    results: dict = {}

    def worker():
        # Should be None in the new thread
        results["before"] = get_current()
        ctx_worker = RunContext.new()
        set_current(ctx_worker)
        results["after"] = get_current()

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert results["before"] is None
    assert results["after"] is not None
    assert results["after"] != ctx_main  # different context
    # Main thread should still have its own
    assert get_current() is ctx_main
    clear_current()


# ---------------------------------------------------------------------------
# with_run_id context manager
# ---------------------------------------------------------------------------


def test_with_run_id_sets_ctx_during_block():
    ctx = RunContext.new()
    clear_current()
    with with_run_id(ctx):
        assert get_current() is ctx
    clear_current()


def test_with_run_id_restores_none_after_block():
    ctx = RunContext.new()
    clear_current()
    with with_run_id(ctx):
        pass
    assert get_current() is None


def test_with_run_id_nested_restores_outer_not_none():
    outer = RunContext.new()
    inner = RunContext.new()
    clear_current()
    with with_run_id(outer):
        assert get_current() is outer
        with with_run_id(inner):
            assert get_current() is inner
        # After inner exits, outer should be restored
        assert get_current() is outer
    assert get_current() is None


def test_with_run_id_restores_on_exception():
    ctx = RunContext.new()
    clear_current()
    with pytest.raises(ValueError), with_run_id(ctx):
        raise ValueError("boom")
    assert get_current() is None


# ---------------------------------------------------------------------------
# inject_headers()
# ---------------------------------------------------------------------------


def test_inject_headers_adds_x_run_id():
    ctx = RunContext.new()
    result = inject_headers(ctx, {})
    assert result["X-Run-Id"] == ctx.run_id


def test_inject_headers_adds_x_parent_run_id_when_parent_set():
    ctx = RunContext.new(parent_id="p456")
    result = inject_headers(ctx, {})
    assert result["X-Parent-Run-Id"] == "p456"


def test_inject_headers_omits_x_parent_run_id_when_no_parent():
    ctx = RunContext.new()
    result = inject_headers(ctx, {})
    assert "X-Parent-Run-Id" not in result


def test_inject_headers_does_not_mutate_input():
    ctx = RunContext.new()
    original = {"Content-Type": "application/json"}
    original_copy = dict(original)
    inject_headers(ctx, original)
    assert original == original_copy


def test_inject_headers_preserves_existing_headers():
    ctx = RunContext.new()
    result = inject_headers(ctx, {"Authorization": "Bearer tok"})
    assert result["Authorization"] == "Bearer tok"
    assert result["X-Run-Id"] == ctx.run_id


# ---------------------------------------------------------------------------
# extract_headers()
# ---------------------------------------------------------------------------


def test_extract_headers_finds_x_run_id():
    ctx = RunContext.new()
    headers = inject_headers(ctx, {})
    extracted = extract_headers(headers)
    assert extracted is not None
    assert extracted.run_id == ctx.run_id


def test_extract_headers_parses_x_parent_run_id():
    ctx = RunContext.new(parent_id="pid789")
    headers = inject_headers(ctx, {})
    extracted = extract_headers(headers)
    assert extracted is not None
    assert extracted.parent_id == "pid789"


def test_extract_headers_case_insensitive_key_lookup():
    # Use all-lowercase header keys
    ctx = RunContext.new()
    headers = {"x-run-id": ctx.run_id}
    extracted = extract_headers(headers)
    assert extracted is not None
    assert extracted.run_id == ctx.run_id


def test_extract_headers_returns_none_when_x_run_id_missing():
    result = extract_headers({"Content-Type": "application/json"})
    assert result is None


def test_extract_headers_no_parent_gives_none_parent_id():
    ctx = RunContext.new()
    # Only inject X-Run-Id, no X-Parent-Run-Id
    headers = {"X-Run-Id": ctx.run_id}
    extracted = extract_headers(headers)
    assert extracted is not None
    assert extracted.parent_id is None


# ---------------------------------------------------------------------------
# inject + extract round-trip
# ---------------------------------------------------------------------------


def test_inject_extract_round_trip():
    ctx = RunContext.new(parent_id="round-trip-parent")
    headers = inject_headers(ctx, {"Accept": "application/json"})
    extracted = extract_headers(headers)
    assert extracted is not None
    assert extracted.run_id == ctx.run_id
    assert extracted.parent_id == ctx.parent_id
