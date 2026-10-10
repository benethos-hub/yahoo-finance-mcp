"""Stage the Claude Desktop bundle (.mcpb) from the checkout.

The bundle is a uv one: it carries the project's pyproject.toml, uv.lock and
source, and Claude Desktop installs the dependencies itself on first start.
This script only copies, so it needs nothing beyond the standard library and
runs the same in CI and locally:

    python .github/publish/mcpb/build.py <staging dir>
    npx @anthropic-ai/mcpb pack <staging dir> <file>.mcpb

The manifest is committed as it ships. tests/test_mcpb.py holds its version,
tools and metadata to the package, and runs this script into a temporary
directory to check what ends up in the bundle.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent

# Destination in the bundle -> source in the checkout.
FILES = {
    "manifest.json": HERE / "manifest.json",
    "server.py": HERE / "server.py",
    "icon.png": REPO / "assets" / "icon.png",
    "pyproject.toml": REPO / "pyproject.toml",
    "uv.lock": REPO / "uv.lock",
    "README.md": REPO / "README.md",
    "LICENSE": REPO / "LICENSE",
}


def stage(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name, source in FILES.items():
        shutil.copy2(source, target / name)
    shutil.copytree(
        REPO / "src",
        target / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"),
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: build.py <staging dir>")
    stage(Path(sys.argv[1]))
    print(f"staged the bundle in {sys.argv[1]}", file=sys.stderr)
