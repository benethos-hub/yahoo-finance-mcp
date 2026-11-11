"""Write the tools and prompts of the bundle manifest from the server.

The manifest is committed as it ships, and two of its lists repeat what the
server registers: every tool with the first sentence of its description, and
every prompt with its text. This writes both from the server itself, so a
changed docstring or recipe needs one command, not a block copied by hand:

    uv run python .github/publish/mcpb/sync_manifest.py

Every other field of the manifest stays as it is. tests/test_mcpb.py fails
while the manifest differs from what this would write, and names the command.
Unlike build.py it needs the project installed, since it asks the server.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

MANIFEST = Path(__file__).resolve().parent / "manifest.json"
COMMAND = "uv run python .github/publish/mcpb/sync_manifest.py"


def first_sentence(text: str) -> str:
    """The tool description cut to its first sentence, as the manifest lists it.

    Claude Desktop shows these lines before installing, so one sentence each.
    An abbreviation like "e.g." does not end the sentence.
    """
    line = " ".join(text.split()).replace("`", "")
    head = re.split(r"(?<!e\.g)(?<!i\.e)\. ", line)[0]
    return head.rstrip(".") + "."


def _server() -> Any:
    from benethos_yahoo_finance_mcp.server import build_server

    return build_server()


def tools(server: Any) -> list[dict[str, str]]:
    """Every tool in listing order, with the first sentence of its description."""
    return [
        {"name": t.name, "description": first_sentence(t.description or "")}
        for t in asyncio.run(server.list_tools())
    ]


def prompts(server: Any) -> list[dict[str, Any]]:
    """Every prompt in listing order, with its text as the server renders it.

    The bundle format writes an argument as ``${arguments.name}``, so the
    server renders each prompt with those placeholders.
    """
    entries = []
    for prompt in asyncio.run(server.list_prompts()):
        names = [a.name for a in prompt.arguments or []]
        placeholders = {n: f"${{arguments.{n}}}" for n in names}
        [message] = asyncio.run(server.get_prompt(prompt.name, placeholders)).messages
        entries.append(
            {
                "name": prompt.name,
                "description": prompt.description,
                "arguments": names,
                "text": message.content.text,
            }
        )
    return entries


def synced(manifest: dict[str, Any], server: Any = None) -> dict[str, Any]:
    """``manifest`` with its tools and prompts as the server has them.

    The key order stays, and prompts follow the tools when there were none.
    """
    server = server or _server()
    fresh = {"tools": tools(server), "prompts": prompts(server)}
    result: dict[str, Any] = {}
    for key, value in manifest.items():
        result[key] = fresh.get(key, value)
        if key == "tools" and "prompts" not in manifest:
            result["prompts"] = fresh["prompts"]
    return result


def write(path: Path = MANIFEST) -> bool:
    """Bring the manifest at ``path`` up to date. True when it changed."""
    before = path.read_text(encoding="utf-8")
    after = json.dumps(synced(json.loads(before)), indent=2, ensure_ascii=False)
    after += "\n"
    if after == before:
        return False
    path.write_text(after, encoding="utf-8", newline="\n")
    return True


if __name__ == "__main__":
    changed = write()
    state = "updated" if changed else "already up to date"
    print(f"{MANIFEST.name}: tools and prompts {state}", file=sys.stderr)
