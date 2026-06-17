# agent-run-id

Generate, format, and thread run IDs through LLM agent pipelines.

Zero runtime dependencies. Pure standard library. Supports hierarchical
sub-run IDs for multi-step agents so you can correlate logs, spans, and
events across a single agent turn.

## Why

When an agent fans out into retrieval, generation, tool calls, and retries,
every log line and trace span should carry an ID that says *which run* and
*which step* it belongs to. `agent-run-id` gives you a tiny, immutable value
object for exactly that, plus an in-process store for threading the active ID
through a request or session.

## Install

```bash
pip install agent-run-id
```

## Usage

```python
from agent_run_id import RunId, RunIdStore

# Generate a run ID for this agent invocation
run_id = RunId.generate()           # RunId('run_7f4a2b1c')
print(run_id.full)                  # "run_7f4a2b1c"

# Create child IDs for sub-steps
step1 = run_id.child("retrieve")    # "run_7f4a2b1c.retrieve"
step2 = run_id.child("generate")    # "run_7f4a2b1c.generate"
attempt = step2.child("attempt_1")  # "run_7f4a2b1c.generate.attempt_1"

# Thread IDs through a session store
store = RunIdStore()
store.set("session:alice", run_id)
store.set("session:bob", RunId.generate())

# In log handlers or spans
print(run_id.as_dict())
# {"run_id": "run_7f4a2b1c", "root_id": "run_7f4a2b1c", "depth": 0}
```

## API

### `RunId`

| Factory | Description |
|---------|-------------|
| `RunId.generate(prefix="run")` | New random ID (`run_<8 hex chars>`). |
| `RunId.from_string(s, prefix="run")` | Wrap an existing string. |

| Method/Property | Description |
|-----------------|-------------|
| `child(label)` | Create a child `RunId` — `full` becomes `{parent}.{label}`. |
| `full` | Full dotted path: `"run_abc"` or `"run_abc.step"`. |
| `short` | Local segment only (no parent). |
| `root` | Walk up to the root `RunId`. |
| `depth` | Nesting depth (0 = root). |
| `as_dict()` | `{"run_id": ..., "root_id": ..., "depth": ...}`. |

### `RunIdStore`

Maps string keys to `RunId` values.

| Method | Description |
|--------|-------------|
| `set(key, run_id)` | Store a run ID. Chainable. |
| `set_new(key, prefix="run")` | Generate, store, and return a new run ID. |
| `get(key, default=None)` | Retrieve a run ID. |
| `require(key)` | Like `get()` but raises `RunIdNotSetError` if absent. |
| `has(key)` | `True` if key exists. |
| `delete(key)` | Remove a key. Chainable. |
| `clear()` | Remove all. Chainable. |
| `keys()` | Sorted list of all keys. |
| `count` | Number of stored IDs. |
| `is_empty` | `True` when no IDs are stored. |

## Equality and hashing

`RunId` is a frozen dataclass, so it is hashable and usable as a dict key or
set member. Equality is based on the **full dotted path** (`value`, `prefix`,
and the entire `parent` chain). Two child IDs that share a label but descend
from different roots are *not* equal:

```python
a = RunId.from_string("aaa").child("step")   # "run_aaa.step"
b = RunId.from_string("bbb").child("step")   # "run_bbb.step"
assert a != b
assert len({a, b}) == 2
```

## Development

```bash
# Run the test suite (standard-library unittest only — no third-party deps):
python3 -m unittest discover -s tests

# Optional lint/format (requires the dev extra):
pip install -e ".[dev]"
ruff check src tests
ruff format --check src tests
```

## License

MIT
