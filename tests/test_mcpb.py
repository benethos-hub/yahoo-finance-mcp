"""Keep the Claude Desktop bundle in step with the package.

The manifest is committed as it ships, so nothing regenerates it on a
release. Its version, its tool list and its metadata repeat what the package
already says, and each of them is held to that here. The bundle itself is
staged by .github/publish/mcpb/build.py, which runs into a temporary
directory below to check what a user's Claude Desktop would unpack.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
import struct
import tomllib
from pathlib import Path

import benethos_yahoo_finance_mcp
from benethos_yahoo_finance_mcp.server import mcp

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / ".github" / "publish" / "mcpb"
MANIFEST = json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))
PROJECT = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))[
    "project"
]


def _first_sentence(text: str) -> str:
    """The tool description cut to its first sentence, as the manifest lists it.

    Claude Desktop shows these lines before installing, so one sentence each.
    An abbreviation like "e.g." does not end the sentence.
    """
    line = " ".join(text.split()).replace("``", "")
    head = re.split(r"(?<!e\.g)(?<!i\.e)\. ", line)[0]
    return head.rstrip(".") + "."


def test_the_version_is_the_package_version():
    assert MANIFEST["version"] == benethos_yahoo_finance_mcp.__version__


def test_the_metadata_is_the_packages():
    assert MANIFEST["name"] == PROJECT["name"]
    assert MANIFEST["description"] == PROJECT["description"]
    assert MANIFEST["author"]["name"] == PROJECT["authors"][0]["name"]
    assert MANIFEST["license"] == PROJECT["license"]["text"]
    assert MANIFEST["compatibility"]["runtimes"]["python"] == PROJECT["requires-python"]


def test_the_tools_are_the_registered_ones():
    """Same tools, same order, each with the first sentence of its description.

    A changed docstring changes the line here too. The expected list is printed
    so it can be pasted into the manifest.
    """
    tools = asyncio.run(mcp.list_tools())
    expected = [
        {"name": t.name, "description": _first_sentence(t.description or "")}
        for t in tools
    ]
    assert MANIFEST["tools"] == expected, json.dumps(expected, indent=2)


def test_it_is_a_uv_bundle_started_from_its_own_directory():
    server = MANIFEST["server"]
    assert MANIFEST["manifest_version"] == "0.4"
    assert server["type"] == "uv"
    assert server["mcp_config"]["command"] == "uv"
    args = server["mcp_config"]["args"]
    assert args[:3] == ["run", "--directory", "${__dirname}"]
    # The lockfile decides the versions, as it does for the image.
    assert "--frozen" in args
    assert args[-1] == server["entry_point"] == "server.py"


def test_the_bundle_reads_no_settings():
    """The server runs without any. An install-time question was judged not
    worth it, the README documents the variables for whoever needs them."""
    assert "user_config" not in MANIFEST
    assert "env" not in MANIFEST["server"]["mcp_config"]


def _load_build_script():
    spec = importlib.util.spec_from_file_location("mcpb_build", BUNDLE / "build.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_staged_bundle_holds_what_uv_needs(tmp_path):
    target = tmp_path / "bundle"
    _load_build_script().stage(target)
    top = sorted(p.name for p in target.iterdir())
    assert top == [
        "LICENSE",
        "README.md",
        "icon.png",
        "manifest.json",
        "pyproject.toml",
        "server.py",
        "src",
        "uv.lock",
    ]
    package = target / "src" / "benethos_yahoo_finance_mcp"
    assert (package / "py.typed").is_file()
    assert not list(target.rglob("__pycache__"))
    assert (target / MANIFEST["icon"]).read_bytes() == (
        REPO / "assets" / "icon.png"
    ).read_bytes()


def test_the_icon_is_the_size_claude_desktop_recommends():
    data = (REPO / "assets" / "icon.png").read_bytes()
    assert struct.unpack(">II", data[16:24]) == (512, 512)
