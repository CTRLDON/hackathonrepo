"""Export every agent's system prompt to prompts/<agent>.md (one file per agent prompt).

The prompts live on the agent classes (agents/<role>.py, attribute `system_prompt`); this script
mirrors them into prompts/ so they can be reviewed and diffed as plain text.
Usage: python scripts/export_prompts.py
"""
from __future__ import annotations
import importlib
import inspect
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agents  # noqa: E402
from agents.base import BaseAgent  # noqa: E402


def collect():
    found = {}
    for mod in pkgutil.iter_modules(agents.__path__):
        if mod.name == "base":
            continue
        module = importlib.import_module(f"agents.{mod.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, BaseAgent) and cls is not BaseAgent and cls.__module__ == module.__name__:
                found[cls.name] = (cls, mod.name)
    return dict(sorted(found.items()))


def export(out_dir: Path = ROOT / "prompts") -> list[Path]:
    out_dir.mkdir(exist_ok=True)
    written = []
    for name, (cls, modname) in collect().items():
        path = out_dir / f"{name}.md"
        path.write_text(
            f"# {cls.__name__} — `{name}`\n\n"
            f"Source: `agents/{modname}.py` (`{cls.__name__}.system_prompt`). "
            f"Exported by `scripts/export_prompts.py`.\n\n"
            f"**Role:** {cls.description or '—'}\n\n"
            f"## System prompt\n\n```text\n{cls.system_prompt.strip()}\n```\n", encoding="utf-8")
        written.append(path)
    print(f"[prompts] {len(written)} files -> {out_dir}")
    return written


if __name__ == "__main__":
    export()
