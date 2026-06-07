"""Tests for agent_run_id (standard-library ``unittest`` only).

Run with::

    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make the ``src`` layout importable when this module is discovered directly
# (``python3 -m unittest discover -s tests``) without first installing the
# package. When the package is installed this is a harmless no-op.
_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent_run_id import RunId, RunIdNotSetError, RunIdStore  # noqa: E402


class GenerateTests(unittest.TestCase):
    def test_generate_returns_run_id(self) -> None:
        self.assertIsInstance(RunId.generate(), RunId)

    def test_generate_default_prefix(self) -> None:
        self.assertTrue(RunId.generate().full.startswith("run_"))

    def test_generate_custom_prefix(self) -> None:
        self.assertTrue(RunId.generate(prefix="req").full.startswith("req_"))

    def test_generate_unique(self) -> None:
        ids = {RunId.generate().full for _ in range(50)}
        self.assertEqual(len(ids), 50)

    def test_generate_format(self) -> None:
        self.assertRegex(RunId.generate().full, r"^run_[0-9a-f]{8}$")


class FromStringTests(unittest.TestCase):
    def test_from_string(self) -> None:
        r = RunId.from_string("abc123")
        self.assertEqual(r.value, "abc123")
        self.assertEqual(r.full, "run_abc123")

    def test_from_string_custom_prefix(self) -> None:
        self.assertEqual(RunId.from_string("xyz", prefix="task").full, "task_xyz")


class HierarchyTests(unittest.TestCase):
    def test_child_full(self) -> None:
        child = RunId.from_string("root").child("step_1")
        self.assertEqual(child.full, "run_root.step_1")

    def test_grandchild_full(self) -> None:
        gc = RunId.from_string("root").child("step_1").child("attempt_2")
        self.assertEqual(gc.full, "run_root.step_1.attempt_2")

    def test_child_short(self) -> None:
        child = RunId.from_string("root").child("step_1")
        self.assertEqual(child.short, "step_1")

    def test_root_short(self) -> None:
        self.assertEqual(RunId.from_string("root").short, "run_root")

    def test_child_inherits_prefix(self) -> None:
        child = RunId.from_string("root", prefix="task").child("s")
        self.assertEqual(child.full, "task_root.s")
        self.assertEqual(child.prefix, "task")

    def test_root_property_at_root(self) -> None:
        r = RunId.from_string("root")
        self.assertIs(r.root, r)

    def test_root_property_from_grandchild(self) -> None:
        root = RunId.from_string("r")
        gc = root.child("a").child("b")
        self.assertIs(gc.root, root)

    def test_depth_root(self) -> None:
        self.assertEqual(RunId.from_string("x").depth, 0)

    def test_depth_child(self) -> None:
        self.assertEqual(RunId.from_string("x").child("y").depth, 1)

    def test_depth_grandchild(self) -> None:
        self.assertEqual(RunId.from_string("x").child("y").child("z").depth, 2)


class StringReprTests(unittest.TestCase):
    def test_str(self) -> None:
        self.assertEqual(str(RunId.from_string("abc")), "run_abc")

    def test_repr(self) -> None:
        self.assertEqual(repr(RunId.from_string("abc")), "RunId('run_abc')")

    def test_str_child(self) -> None:
        self.assertEqual(str(RunId.from_string("abc").child("s")), "run_abc.s")


class AsDictTests(unittest.TestCase):
    def test_as_dict_root(self) -> None:
        d = RunId.from_string("abc").as_dict()
        self.assertEqual(d["run_id"], "run_abc")
        self.assertEqual(d["root_id"], "run_abc")
        self.assertEqual(d["depth"], 0)

    def test_as_dict_child(self) -> None:
        d = RunId.from_string("root").child("s1").as_dict()
        self.assertEqual(d["run_id"], "run_root.s1")
        self.assertEqual(d["root_id"], "run_root")
        self.assertEqual(d["depth"], 1)


class EqualityTests(unittest.TestCase):
    def test_equality_same_value(self) -> None:
        self.assertEqual(
            RunId(value="abc", prefix="run"),
            RunId(value="abc", prefix="run"),
        )

    def test_inequality_different_value(self) -> None:
        self.assertNotEqual(
            RunId(value="abc", prefix="run"),
            RunId(value="xyz", prefix="run"),
        )

    def test_inequality_different_prefix(self) -> None:
        self.assertNotEqual(
            RunId(value="abc", prefix="run"),
            RunId(value="abc", prefix="task"),
        )

    def test_equality_same_full_path(self) -> None:
        a = RunId.from_string("root").child("step")
        b = RunId.from_string("root").child("step")
        self.assertEqual(a, b)

    def test_inequality_different_parent(self) -> None:
        # Regression: children with the same label but different parents
        # produce different full paths and must NOT compare equal.
        a = RunId.from_string("aaa").child("step")
        b = RunId.from_string("bbb").child("step")
        self.assertNotEqual(a, b)
        self.assertNotEqual(a.full, b.full)

    def test_hashable_and_distinct_by_path(self) -> None:
        a = RunId.from_string("aaa").child("step")
        b = RunId.from_string("bbb").child("step")
        c = RunId.from_string("aaa").child("step")
        self.assertEqual(len({a, b, c}), 2)


class StoreBasicTests(unittest.TestCase):
    def test_store_repr(self) -> None:
        self.assertIn("count=0", repr(RunIdStore()))

    def test_store_initial_empty(self) -> None:
        store = RunIdStore()
        self.assertEqual(store.count, 0)
        self.assertTrue(store.is_empty)

    def test_store_set_and_get(self) -> None:
        store = RunIdStore()
        r = RunId.from_string("abc")
        store.set("sess:1", r)
        self.assertEqual(store.get("sess:1"), r)

    def test_store_set_returns_self(self) -> None:
        store = RunIdStore()
        self.assertIs(store.set("k", RunId.from_string("v")), store)

    def test_store_get_missing_default(self) -> None:
        self.assertIsNone(RunIdStore().get("missing"))

    def test_store_get_custom_default(self) -> None:
        default = RunId.from_string("fallback")
        self.assertIs(RunIdStore().get("missing", default), default)

    def test_store_has(self) -> None:
        store = RunIdStore()
        store.set("k", RunId.from_string("v"))
        self.assertTrue(store.has("k"))
        self.assertFalse(store.has("nope"))

    def test_store_contains(self) -> None:
        store = RunIdStore()
        store.set("k", RunId.from_string("v"))
        self.assertIn("k", store)
        self.assertNotIn("other", store)

    def test_store_len(self) -> None:
        store = RunIdStore()
        store.set("a", RunId.from_string("x"))
        self.assertEqual(len(store), 1)

    def test_store_overwrite(self) -> None:
        store = RunIdStore()
        first = RunId.from_string("first")
        second = RunId.from_string("second")
        store.set("k", first).set("k", second)
        self.assertEqual(store.get("k"), second)
        self.assertEqual(store.count, 1)


class StoreSetNewTests(unittest.TestCase):
    def test_set_new_generates_and_stores(self) -> None:
        store = RunIdStore()
        r = store.set_new("sess:1")
        self.assertIsInstance(r, RunId)
        self.assertIs(store.get("sess:1"), r)

    def test_set_new_custom_prefix(self) -> None:
        self.assertTrue(RunIdStore().set_new("k", prefix="req").full.startswith("req_"))


class StoreRequireTests(unittest.TestCase):
    def test_require_present(self) -> None:
        store = RunIdStore()
        r = RunId.from_string("abc")
        store.set("k", r)
        self.assertEqual(store.require("k"), r)

    def test_require_missing_raises(self) -> None:
        with self.assertRaises(RunIdNotSetError):
            RunIdStore().require("missing")

    def test_run_id_not_set_error_is_key_error(self) -> None:
        self.assertTrue(issubclass(RunIdNotSetError, KeyError))


class StoreDeleteClearTests(unittest.TestCase):
    def test_delete(self) -> None:
        store = RunIdStore()
        store.set("k", RunId.from_string("v"))
        store.delete("k")
        self.assertFalse(store.has("k"))

    def test_delete_noop(self) -> None:
        store = RunIdStore()
        store.delete("nonexistent")
        self.assertEqual(store.count, 0)

    def test_delete_returns_self(self) -> None:
        store = RunIdStore()
        self.assertIs(store.delete("k"), store)

    def test_clear(self) -> None:
        store = RunIdStore()
        store.set("a", RunId.from_string("x"))
        store.set("b", RunId.from_string("y"))
        store.clear()
        self.assertEqual(store.count, 0)

    def test_clear_returns_self(self) -> None:
        store = RunIdStore()
        self.assertIs(store.clear(), store)


class StoreKeysTests(unittest.TestCase):
    def test_keys_sorted(self) -> None:
        store = RunIdStore()
        store.set("z", RunId.from_string("1"))
        store.set("a", RunId.from_string("2"))
        self.assertEqual(store.keys(), ["a", "z"])


if __name__ == "__main__":
    unittest.main()
