"""Keep the Claude Desktop bundle in step with the package.

The manifest is committed as it ships, so nothing regenerates it on a
release. Its version, its tool list and its metadata repeat what the package
already says, and each of them is held to that here. The bundle itself is
staged by .github/publish/mcpb/build.py, which runs into a temporary
directory below to check what a user's Claude Desktop would unpack.
"""

from __future__ import annotations

import importlib.util
import json
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


def test_the_version_is_the_package_version():
    assert MANIFEST["version"] == benethos_yahoo_finance_mcp.__version__


def test_the_metadata_is_the_packages():
    assert MANIFEST["name"] == PROJECT["name"]
    assert MANIFEST["description"] == PROJECT["description"]
    assert MANIFEST["author"]["name"] == PROJECT["authors"][0]["name"]
    assert MANIFEST["license"] == PROJECT["license"]["text"]
    assert MANIFEST["compatibility"]["runtimes"]["python"] == PROJECT["requires-python"]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"mcpb_{name}", BUNDLE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SYNC = _load_script("sync_manifest")
SYNCED = SYNC.synced(MANIFEST, mcp)


def test_the_tools_are_the_registered_ones():
    """Same tools, same order, each with the first sentence of its description.

    A changed docstring changes the line here too, and sync_manifest.py
    writes it.
    """
    assert MANIFEST["tools"] == SYNCED["tools"], f"run: {SYNC.COMMAND}"


def test_the_prompts_are_the_registered_ones():
    """Same prompts, same order, the text as the server renders it."""
    assert MANIFEST["prompts"] == SYNCED["prompts"], f"run: {SYNC.COMMAND}"


def test_syncing_touches_nothing_but_tools_and_prompts(tmp_path):
    """A stale manifest comes back whole, every other field and the key order
    as they were, and a second run finds nothing to do."""
    stale = dict(MANIFEST, tools=[], prompts=[{"name": "gone"}])
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(stale, indent=2), encoding="utf-8")
    first = SYNC.write(path)
    assert first is True
    assert path.read_text(encoding="utf-8") == (BUNDLE / "manifest.json").read_text(
        encoding="utf-8"
    )
    second = SYNC.write(path)
    assert second is False


def test_the_first_sentence_stops_at_a_full_stop_but_not_an_abbreviation():
    assert SYNC.first_sentence("Find stocks, e.g. cheap ones. More.") == (
        "Find stocks, e.g. cheap ones."
    )
    assert SYNC.first_sentence("Get `the` quote") == "Get the quote."


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
    return _load_script("build")


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
        REPO / "assets" / "brand" / "icon.png"
    ).read_bytes()


def test_the_icon_is_the_size_claude_desktop_recommends():
    data = (REPO / "assets" / "brand" / "icon.png").read_bytes()
    assert struct.unpack(">II", data[16:24]) == (512, 512)


# --- the auto-update bundle -----------------------------------------------


def test_the_auto_update_manifest_is_the_pinned_one_in_all_but_its_own_fields():
    """Version and tools come from the pinned manifest, so they cannot drift."""
    build = _load_build_script()
    manifest = build.auto_update_manifest()
    own = set(build.AUTO_UPDATE) | set(build.AUTO_UPDATE_DROPPED)
    assert own == {
        "name",
        "display_name",
        "description",
        "server",
        "tools_generated",
        "prompts_generated",
        "prompts",
    }
    assert {k: v for k, v in manifest.items() if k not in own} == {
        k: v for k, v in MANIFEST.items() if k not in own
    }
    assert manifest["version"] == benethos_yahoo_finance_mcp.__version__
    # Its own description opens as the project's does, so a new one in
    # pyproject.toml cannot leave this card behind.
    opening = MANIFEST["description"].split("(via yfinance)")[0] + "(via yfinance)"
    assert manifest["description"].startswith(opening)


def test_the_auto_update_bundle_stands_beside_the_pinned_one():
    """Claude Desktop keys an extension by its name, the same one would replace it."""
    manifest = _load_build_script().auto_update_manifest()
    assert manifest["name"] == PROJECT["name"] + "-auto-update"
    assert manifest["display_name"] != MANIFEST["display_name"]
    assert "auto-update" in manifest["display_name"]


def test_the_auto_update_manifest_declares_no_prompt_a_later_release_could_contradict():
    """It stays at the release it was installed from while the server moves
    on. A client may check the prompts against the manifest, so it names none
    and says the server makes them, and the tools beyond its list."""
    manifest = _load_build_script().auto_update_manifest()
    assert "prompts" not in manifest
    assert manifest["prompts_generated"] is True
    assert manifest["tools_generated"] is True
    # The pinned bundle ships its manifest with its code, so it lists both.
    assert MANIFEST["prompts"]
    assert "prompts_generated" not in MANIFEST


def test_the_auto_update_bundle_runs_the_newest_release_from_the_index():
    server = _load_build_script().auto_update_manifest()["server"]
    assert server["type"] == "uv"
    assert server["mcp_config"]["command"] == "uv"
    # No version, no lockfile, no directory: uv resolves the newest release.
    assert server["mcp_config"]["args"] == ["tool", "run", PROJECT["name"]]
    assert "env" not in server["mcp_config"]


def test_the_staged_auto_update_bundle_carries_no_project(tmp_path):
    """Without a pyproject.toml Claude Desktop has nothing to install."""
    build = _load_build_script()
    target = tmp_path / "auto-update"
    build.stage_auto_update(target)
    assert sorted(p.name for p in target.iterdir()) == [
        "LICENSE",
        "icon.png",
        "manifest.json",
    ]
    staged = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert staged == build.auto_update_manifest()
    assert (target / staged["icon"]).read_bytes() == (
        REPO / "assets" / "brand" / "icon.png"
    ).read_bytes()
