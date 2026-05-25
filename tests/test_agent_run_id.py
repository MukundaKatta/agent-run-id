"""Tests for agent_run_id."""

from __future__ import annotations

import re

import pytest

from agent_run_id import RunId, RunIdNotSetError, RunIdStore

# ---------------------------------------------------------------------------
# RunId.generate
# ---------------------------------------------------------------------------


def test_generate_returns_run_id():
    r = RunId.generate()
    assert isinstance(r, RunId)


def test_generate_default_prefix():
    r = RunId.generate()
    assert r.full.startswith("run_")


def test_generate_custom_prefix():
    r = RunId.generate(prefix="req")
    assert r.full.startswith("req_")


def test_generate_unique():
    ids = {RunId.generate().full for _ in range(20)}
    assert len(ids) == 20


def test_generate_format():
    r = RunId.generate()
    assert re.match(r"^run_[0-9a-f]{8}$", r.full)


# ---------------------------------------------------------------------------
# RunId.from_string
# ---------------------------------------------------------------------------


def test_from_string():
    r = RunId.from_string("abc123")
    assert r.value == "abc123"
    assert r.full == "run_abc123"


def test_from_string_custom_prefix():
    r = RunId.from_string("xyz", prefix="task")
    assert r.full == "task_xyz"


# ---------------------------------------------------------------------------
# RunId hierarchy
# ---------------------------------------------------------------------------


def test_child_full():
    root = RunId.from_string("root")
    child = root.child("step_1")
    assert child.full == "run_root.step_1"


def test_grandchild_full():
    root = RunId.from_string("root")
    child = root.child("step_1")
    grandchild = child.child("attempt_2")
    assert grandchild.full == "run_root.step_1.attempt_2"


def test_child_short():
    root = RunId.from_string("root")
    child = root.child("step_1")
    assert child.short == "step_1"


def test_root_short():
    r = RunId.from_string("root")
    assert r.short == "run_root"


def test_root_property_at_root():
    r = RunId.from_string("root")
    assert r.root is r


def test_root_property_from_grandchild():
    root = RunId.from_string("r")
    gc = root.child("a").child("b")
    assert gc.root is root


def test_depth_root():
    r = RunId.from_string("x")
    assert r.depth == 0


def test_depth_child():
    root = RunId.from_string("x")
    assert root.child("y").depth == 1


def test_depth_grandchild():
    root = RunId.from_string("x")
    assert root.child("y").child("z").depth == 2


# ---------------------------------------------------------------------------
# RunId string / repr
# ---------------------------------------------------------------------------


def test_str():
    r = RunId.from_string("abc")
    assert str(r) == "run_abc"


def test_repr():
    r = RunId.from_string("abc")
    assert repr(r) == "RunId('run_abc')"


# ---------------------------------------------------------------------------
# RunId as_dict
# ---------------------------------------------------------------------------


def test_as_dict_root():
    r = RunId.from_string("abc")
    d = r.as_dict()
    assert d["run_id"] == "run_abc"
    assert d["root_id"] == "run_abc"
    assert d["depth"] == 0


def test_as_dict_child():
    root = RunId.from_string("root")
    child = root.child("s1")
    d = child.as_dict()
    assert d["run_id"] == "run_root.s1"
    assert d["root_id"] == "run_root"
    assert d["depth"] == 1


# ---------------------------------------------------------------------------
# RunId equality (frozen dataclass)
# ---------------------------------------------------------------------------


def test_equality_same_value():
    a = RunId(value="abc", prefix="run")
    b = RunId(value="abc", prefix="run")
    assert a == b


def test_inequality_different_value():
    a = RunId(value="abc", prefix="run")
    b = RunId(value="xyz", prefix="run")
    assert a != b


# ---------------------------------------------------------------------------
# RunIdStore — basic ops
# ---------------------------------------------------------------------------


def test_store_repr():
    store = RunIdStore()
    assert "count=0" in repr(store)


def test_store_initial_empty():
    store = RunIdStore()
    assert store.count == 0
    assert store.is_empty is True


def test_store_set_and_get():
    store = RunIdStore()
    r = RunId.from_string("abc")
    store.set("sess:1", r)
    assert store.get("sess:1") == r


def test_store_set_returns_self():
    store = RunIdStore()
    assert store.set("k", RunId.from_string("v")) is store


def test_store_get_missing_default():
    store = RunIdStore()
    assert store.get("missing") is None


def test_store_get_custom_default():
    store = RunIdStore()
    default = RunId.from_string("fallback")
    assert store.get("missing", default) is default


def test_store_has():
    store = RunIdStore()
    store.set("k", RunId.from_string("v"))
    assert store.has("k") is True
    assert store.has("nope") is False


def test_store_contains():
    store = RunIdStore()
    store.set("k", RunId.from_string("v"))
    assert "k" in store
    assert "other" not in store


def test_store_len():
    store = RunIdStore()
    store.set("a", RunId.from_string("x"))
    assert len(store) == 1


# ---------------------------------------------------------------------------
# RunIdStore — set_new
# ---------------------------------------------------------------------------


def test_set_new_generates_and_stores():
    store = RunIdStore()
    r = store.set_new("sess:1")
    assert isinstance(r, RunId)
    assert store.get("sess:1") is r


def test_set_new_custom_prefix():
    store = RunIdStore()
    r = store.set_new("k", prefix="req")
    assert r.full.startswith("req_")


# ---------------------------------------------------------------------------
# RunIdStore — require
# ---------------------------------------------------------------------------


def test_require_present():
    store = RunIdStore()
    r = RunId.from_string("abc")
    store.set("k", r)
    assert store.require("k") == r


def test_require_missing_raises():
    with pytest.raises(RunIdNotSetError):
        RunIdStore().require("missing")


def test_run_id_not_set_error_is_key_error():
    assert issubclass(RunIdNotSetError, KeyError)


# ---------------------------------------------------------------------------
# RunIdStore — delete / clear
# ---------------------------------------------------------------------------


def test_delete():
    store = RunIdStore()
    store.set("k", RunId.from_string("v"))
    store.delete("k")
    assert store.has("k") is False


def test_delete_noop():
    store = RunIdStore()
    store.delete("nonexistent")
    assert store.count == 0


def test_delete_returns_self():
    store = RunIdStore()
    assert store.delete("k") is store


def test_clear():
    store = RunIdStore()
    store.set("a", RunId.from_string("x"))
    store.set("b", RunId.from_string("y"))
    store.clear()
    assert store.count == 0


def test_clear_returns_self():
    store = RunIdStore()
    assert store.clear() is store


# ---------------------------------------------------------------------------
# RunIdStore — keys
# ---------------------------------------------------------------------------


def test_keys_sorted():
    store = RunIdStore()
    store.set("z", RunId.from_string("1"))
    store.set("a", RunId.from_string("2"))
    assert store.keys() == ["a", "z"]
