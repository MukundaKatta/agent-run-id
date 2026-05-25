# agent-run-id

Generate and propagate run IDs through agent loops. Zero dependencies.

```python
from agent_run_id import RunContext, tag_messages, strip_tags, annotate

with RunContext() as ctx:
    tagged = tag_messages(messages, ctx.run_id)
    response = client.messages.create(messages=strip_tags(tagged))
    log_entry = annotate({"event": "llm_call"})  # adds run_id automatically
```

## Install

```bash
pip install agent-run-id
```
