import pytest
from agent_run_id import (
    RunId, RunContext, generate_run_id, make_run_id,
    tag_message, tag_messages, strip_tag, strip_tags, extract_run_id,
    set_current_run_id, get_current_run_id, require_run_id, clear_run_id,
    annotate,
)


# ---------------------------------------------------------------------------
# generate_run_id
# ---------------------------------------------------------------------------

def test_generate_run_id_default_prefix():
    rid = generate_run_id()
    assert rid.startswith("run_")

def test_generate_run_id_custom_prefix():
    rid = generate_run_id("agent")
    assert rid.startswith("agent_")

def test_generate_run_id_empty_prefix():
    rid = generate_run_id("")
    assert "_" not in rid[:1]  # no leading underscore

def test_generate_run_id_unique():
    ids = {generate_run_id() for _ in range(100)}
    assert len(ids) == 100

def test_generate_run_id_returns_str():
    assert isinstance(generate_run_id(), str)


# ---------------------------------------------------------------------------
# make_run_id / RunId
# ---------------------------------------------------------------------------

def test_make_run_id_returns_run_id():
    rid = make_run_id()
    assert isinstance(rid, RunId)

def test_run_id_str():
    rid = make_run_id()
    assert str(rid) == rid.id

def test_run_id_short_length():
    rid = make_run_id()
    assert len(rid.short) == 8

def test_run_id_short_no_prefix():
    rid = RunId(id="run_abcdef1234567890", prefix="run")
    assert rid.short == "abcdef12"

def test_run_id_created_at():
    import time
    before = time.time()
    rid = make_run_id()
    after = time.time()
    assert before <= rid.created_at <= after

def test_run_id_repr():
    rid = RunId(id="run_abc")
    assert "run_abc" in repr(rid)

def test_run_id_prefix_stored():
    rid = make_run_id("session")
    assert rid.prefix == "session"
    assert rid.id.startswith("session_")


# ---------------------------------------------------------------------------
# tag_message / strip_tag / extract_run_id
# ---------------------------------------------------------------------------

def test_tag_message_adds_key():
    msg = {"role": "user", "content": "hi"}
    tagged = tag_message(msg, "run_abc")
    assert "_run_id" in tagged

def test_tag_message_does_not_mutate():
    msg = {"role": "user", "content": "hi"}
    tag_message(msg, "run_abc")
    assert "_run_id" not in msg

def test_tag_message_run_id_value():
    msg = {"role": "user", "content": "hi"}
    rid = make_run_id()
    tagged = tag_message(msg, rid)
    assert tagged["_run_id"] == str(rid)

def test_tag_messages_all_tagged():
    msgs = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    tagged = tag_messages(msgs, "run_x")
    for t in tagged:
        assert t["_run_id"] == "run_x"

def test_strip_tag_removes_key():
    msg = {"role": "user", "content": "hi", "_run_id": "run_abc"}
    stripped = strip_tag(msg)
    assert "_run_id" not in stripped

def test_strip_tag_does_not_mutate():
    msg = {"role": "user", "content": "hi", "_run_id": "run_abc"}
    strip_tag(msg)
    assert "_run_id" in msg

def test_strip_tags_all_stripped():
    msgs = [
        {"role": "user", "content": "a", "_run_id": "x"},
        {"role": "assistant", "content": "b", "_run_id": "x"},
    ]
    stripped = strip_tags(msgs)
    for m in stripped:
        assert "_run_id" not in m

def test_extract_run_id_present():
    msg = {"role": "user", "content": "hi", "_run_id": "run_abc"}
    assert extract_run_id(msg) == "run_abc"

def test_extract_run_id_absent():
    msg = {"role": "user", "content": "hi"}
    assert extract_run_id(msg) is None

def test_round_trip_tag_strip():
    msg = {"role": "user", "content": "hi"}
    rid = "run_xyz"
    tagged = tag_message(msg, rid)
    stripped = strip_tag(tagged)
    assert stripped == msg


# ---------------------------------------------------------------------------
# Context variable
# ---------------------------------------------------------------------------

def test_get_current_run_id_default_none():
    clear_run_id()
    assert get_current_run_id() is None

def test_set_get_current_run_id():
    rid = make_run_id()
    set_current_run_id(rid)
    got = get_current_run_id()
    assert got is rid
    clear_run_id()

def test_set_string_wrapped():
    set_current_run_id("run_abc")
    got = get_current_run_id()
    assert isinstance(got, RunId)
    assert got.id == "run_abc"
    clear_run_id()

def test_require_run_id_raises_when_none():
    clear_run_id()
    with pytest.raises(RuntimeError):
        require_run_id()

def test_require_run_id_returns_when_set():
    rid = make_run_id()
    set_current_run_id(rid)
    got = require_run_id()
    assert got is rid
    clear_run_id()

def test_clear_run_id():
    set_current_run_id(make_run_id())
    clear_run_id()
    assert get_current_run_id() is None


# ---------------------------------------------------------------------------
# RunContext
# ---------------------------------------------------------------------------

def test_run_context_sets_run_id():
    clear_run_id()
    with RunContext() as ctx:
        assert get_current_run_id() is ctx.run_id

def test_run_context_restores_on_exit():
    clear_run_id()
    with RunContext():
        pass
    assert get_current_run_id() is None

def test_run_context_auto_generates():
    with RunContext() as ctx:
        assert ctx.run_id is not None
        assert ctx.run_id.id.startswith("run_")

def test_run_context_custom_run_id():
    rid = make_run_id("job")
    with RunContext(run_id=rid) as ctx:
        assert ctx.run_id is rid

def test_run_context_string_run_id():
    with RunContext(run_id="run_custom123") as ctx:
        assert ctx.run_id.id == "run_custom123"

def test_run_context_prefix():
    with RunContext(prefix="session") as ctx:
        assert ctx.run_id.id.startswith("session_")

def test_run_context_nested():
    outer = make_run_id()
    inner = make_run_id()
    with RunContext(run_id=outer):
        assert get_current_run_id().id == outer.id
        with RunContext(run_id=inner):
            assert get_current_run_id().id == inner.id
        assert get_current_run_id().id == outer.id


# ---------------------------------------------------------------------------
# annotate
# ---------------------------------------------------------------------------

def test_annotate_with_explicit_run_id():
    data = {"event": "tool_call", "tool": "search"}
    result = annotate(data, run_id="run_abc")
    assert result["run_id"] == "run_abc"

def test_annotate_uses_context():
    data = {"event": "llm_call"}
    with RunContext(run_id="run_ctx123") as ctx:
        result = annotate(data)
    assert result["run_id"] == "run_ctx123"

def test_annotate_no_run_id_no_context():
    clear_run_id()
    data = {"event": "log"}
    result = annotate(data)
    assert "run_id" not in result

def test_annotate_does_not_mutate():
    data = {"event": "log"}
    annotate(data, run_id="run_abc")
    assert "run_id" not in data

def test_annotate_custom_key():
    data = {"event": "log"}
    result = annotate(data, run_id="run_abc", key="trace_id")
    assert result["trace_id"] == "run_abc"
    assert "run_id" not in result
