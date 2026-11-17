# prompts/

One file per agent: each file mirrors that agent's `system_prompt` from `agents/<role>.py`, exported by
`python scripts/export_prompts.py` (`make prompts`). The per-call instructions and JSON schemas each agent sends
with a request live next to the call in `agents/<role>.py`.
