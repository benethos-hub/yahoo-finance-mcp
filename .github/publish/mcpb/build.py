"""Stage the Claude Desktop bundles (.mcpb) from the checkout.

There are two. The pinned bundle is a uv one that carries the project's
pyproject.toml, uv.lock and source, and Claude Desktop installs exactly those
versions on first start. The auto-update bundle carries no code: it has
Claude Desktop run ``uv tool run benethos-yahoo-finance-mcp``, which starts
the newest release on PyPI, so a new release arrives with a restart of
Claude Desktop, without a new bundle. This script only copies, so it needs
nothing beyond the standard library and runs the same in CI and locally:

    uv run --no-project .github/publish/mcpb/build.py <staging dir>
    uv run --no-project .github/publish/mcpb/build.py --auto-update <staging dir>

In a release, the organisation's publish/mcpb action validates and packs each
staged tree and attaches it. Locally, the mcpb CLI packs it:

    npx @anthropic-ai/mcpb pack <staging dir> <file>.mcpb

The pinned manifest is committed as it ships. The auto-update one is made
from it here, so its version and tool list cannot drift from it. It leaves
the prompts out, since it outlives the release that built it.
tests/test_mcpb.py holds both to the package, and runs this script into a
temporary directory to check what ends up in each bundle.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent

# Destination in the bundle -> source in the checkout.
FILES = {
    "manifest.json": HERE / "manifest.json",
    "server.py": HERE / "server.py",
    "icon.png": REPO / "assets" / "brand" / "icon.png",
    "pyproject.toml": REPO / "pyproject.toml",
    "uv.lock": REPO / "uv.lock",
    "README.md": REPO / "README.md",
    "LICENSE": REPO / "LICENSE",
}


# The auto-update bundle: what it changes in the pinned manifest. Its own
# name keeps it apart from the pinned bundle in Claude Desktop, which would
# otherwise replace one with the other. The version stays the release's, the
# organisation's action holds it to the tag, and it only says which release
# built the bundle, not which one runs.
AUTO_UPDATE = {
    "name": "benethos-yahoo-finance-mcp-auto-update",
    "display_name": "Unofficial Yahoo Finance MCP Server (auto-update)",
    "description": (
        "Unofficial read-only MCP server exposing Yahoo Finance data (via "
        "yfinance). Starts the newest release from PyPI, so a new release "
        "arrives with a restart of Claude Desktop."
    ),
    "server": {
        "type": "uv",
        "entry_point": "benethos-yahoo-finance-mcp",
        "mcp_config": {
            "command": "uv",
            "args": ["tool", "run", "benethos-yahoo-finance-mcp"],
        },
    },
    # Installed once, this manifest stays at its release while the server
    # moves on with every new one. The bundle format lets a client check the
    # prompts a server offers against the ones declared here, so a later
    # release with a changed recipe could be refused. It declares none and
    # says the server makes them, and the same for tools beyond its list.
    "tools_generated": True,
    "prompts_generated": True,
}

# Fields of the pinned manifest the auto-update one leaves out, see above.
AUTO_UPDATE_DROPPED = ("prompts",)

# Destination in the auto-update bundle -> source. No pyproject.toml, so
# Claude Desktop has no project to install, only the command to run.
AUTO_UPDATE_FILES = {
    "icon.png": FILES["icon.png"],
    "LICENSE": FILES["LICENSE"],
}


def _fresh(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)


def _copy(files: dict[str, Path], target: Path) -> None:
    _fresh(target)
    for name, source in files.items():
        shutil.copy2(source, target / name)


def stage(target: Path) -> None:
    _copy(FILES, target)
    shutil.copytree(
        REPO / "src",
        target / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )


def auto_update_manifest() -> dict[str, object]:
    """The pinned manifest with the fields of ``AUTO_UPDATE`` in its place,
    and without those of ``AUTO_UPDATE_DROPPED``."""
    manifest = json.loads(FILES["manifest.json"].read_text(encoding="utf-8"))
    for field in AUTO_UPDATE_DROPPED:
        manifest.pop(field, None)
    manifest.update(AUTO_UPDATE)
    return manifest


def stage_auto_update(target: Path) -> None:
    _copy(AUTO_UPDATE_FILES, target)
    (target / "manifest.json").write_text(
        json.dumps(auto_update_manifest(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    auto_update = args[:1] == ["--auto-update"]
    if auto_update:
        args = args[1:]
    if len(args) != 1:
        sys.exit("usage: build.py [--auto-update] <staging dir>")
    (stage_auto_update if auto_update else stage)(Path(args[0]))
    kind = "auto-update bundle" if auto_update else "bundle"
    print(f"staged the {kind} in {args[0]}", file=sys.stderr)
