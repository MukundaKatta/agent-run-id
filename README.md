# agent-run-id

Generate, format, and thread run IDs through LLM agent pipelines.

Zero dependencies. Supports hierarchical sub-run IDs for multi-step agents.

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

## License

MIT
