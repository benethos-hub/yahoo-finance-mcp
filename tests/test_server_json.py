"""Keep server.json, the MCP Registry entry, in step with the package.

The registry takes one entry per version and never lets it be changed, so a
mistake in it stays published until the next release. It also checks
ownership on its own side: the README of that version on PyPI must carry an
``mcp-name:`` line and the image config a label, both naming the entry. Each
of those lives in a different file, and nothing but this suite reads them
together before the release workflow sends the entry.
"""

from __future__ import annotations

import json
import re
import struct
import tomllib
from pathlib import Path

import pytest

import benethos_yahoo_finance_mcp
from benethos_yahoo_finance_mcp import settings

REPO = Path(__file__).resolve().parent.parent
SERVER = json.loads(
    (REPO / ".github/publish/mcp-registry/server.json").read_text(encoding="utf-8")
)
PROJECT = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))[
    "project"
]
NAME = SERVER["name"]
IMAGE = "ghcr.io/benethos-hub/benethos-yahoo-finance-mcp"


def _package(registry_type: str) -> dict:
    (package,) = [p for p in SERVER["packages"] if p["registryType"] == registry_type]
    return package


def test_the_name_sits_in_this_repositorys_github_namespace():
    """The release workflow logs in with this repository's OIDC token, and the
    registry grants that token the io.github.<owner>/ namespace only."""
    owner = (
        SERVER["repository"]["url"].removeprefix("https://github.com/").split("/")[0]
    )
    assert NAME.startswith(f"io.github.{owner}/"), (
        f"{NAME} is outside io.github.{owner}/, so the workflow cannot publish it"
    )


def test_every_version_is_the_package_version():
    current = benethos_yahoo_finance_mcp.__version__
    tag = _package("oci")["identifier"].rpartition(":")[2]
    versions = {
        "version": SERVER["version"],
        "the PyPI package": _package("pypi")["version"],
        "the image tag": tag,
    }
    stale = {where: v for where, v in versions.items() if v != current}
    assert not stale, (
        f"server.json still says {stale}, the package is at {current}. The "
        "registry would list an entry pointing at the release before this one."
    )


def test_the_packages_are_this_distribution_and_its_image():
    assert _package("pypi")["identifier"] == PROJECT["name"]
    assert _package("oci")["identifier"].rpartition(":")[0] == IMAGE


def test_the_description_is_the_package_description():
    """One sentence for both, and the registry stops at 100 characters."""
    assert SERVER["description"] == PROJECT["description"]
    assert len(SERVER["description"]) <= 100


def test_the_readme_carries_the_name_for_pypi():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    # The registry wants the token followed by a boundary, a space, a newline
    # or the close of a comment, never glued to a full stop.
    assert re.findall(r"mcp-name: (\S+)(?=\s|-->)", readme) == [NAME]


def test_the_image_label_carries_the_name():
    dockerfile = (REPO / "containers/images/yahoo-finance-mcp/Dockerfile").read_text(
        encoding="utf-8"
    )
    labels = re.findall(
        r'^LABEL io\.modelcontextprotocol\.server\.name="([^"]+)"', dockerfile, re.M
    )
    assert labels == [NAME]


def test_the_icon_is_a_file_of_this_repository():
    """The URL points at main, so the file has to be on main to be found."""
    prefix = "https://raw.githubusercontent.com/benethos-hub/yahoo-finance-mcp/main/"
    for icon in SERVER["icons"]:
        assert icon["src"].startswith(prefix)
        assert (REPO / icon["src"].removeprefix(prefix)).is_file()


def test_the_png_icon_has_the_size_the_entry_states():
    """assets/render_icon.py writes the PNG, and a change of its SIZE without
    the entry, or the other way round, would advertise a size that is not
    there. A PNG states its width and height at bytes 16 to 24."""
    prefix = "https://raw.githubusercontent.com/benethos-hub/yahoo-finance-mcp/main/"
    for icon in SERVER["icons"]:
        if icon["mimeType"] != "image/png":
            continue
        data = (REPO / icon["src"].removeprefix(prefix)).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", data[16:24])
        assert icon["sizes"] == [f"{width}x{height}"]


# The options a client offers at install time. Each one must be a variable
# the server reads, its default must be what the server does without it, and
# every value the entry lets a person pick must be one the server takes. A
# renamed variable or a changed default would otherwise stay advertised in
# an entry that can no longer be corrected.
OPTIONS = _package("pypi").get("environmentVariables", [])
SETTINGS_SOURCE = Path(settings.__file__).read_text(encoding="utf-8")


def test_the_entry_offers_options():
    assert OPTIONS, "the PyPI package lists no environment variables"


@pytest.mark.parametrize("option", OPTIONS, ids=lambda o: o["name"])
def test_each_option_is_a_variable_the_server_reads(option):
    assert f'"{option["name"]}"' in SETTINGS_SOURCE
    assert not option.get("isRequired", False), "the server runs without any"


@pytest.mark.parametrize(
    "option", [o for o in OPTIONS if "default" in o], ids=lambda o: o["name"]
)
def test_each_default_is_what_the_server_does_without_it(option):
    unset = settings.load_settings(environ={})
    as_default = settings.load_settings(environ={option["name"]: option["default"]})
    assert not as_default.ignored, f"{option['default']!r} is refused"
    assert as_default == unset


@pytest.mark.parametrize(
    "option", [o for o in OPTIONS if "choices" in o], ids=lambda o: o["name"]
)
def test_each_choice_is_taken(option):
    for choice in option["choices"]:
        resolved = settings.load_settings(environ={option["name"]: choice})
        assert not resolved.ignored, f"{option['name']}={choice!r} is refused"


def test_the_log_level_choices_are_the_servers():
    (level,) = [o for o in OPTIONS if o["name"] == "YF_MCP_LOG_LEVEL"]
    assert tuple(level["choices"]) == settings.LOG_LEVELS


def test_a_boolean_option_is_switched_by_true():
    """A client renders a boolean as a switch and passes true or false."""
    cache = settings.load_settings(
        environ={"YF_MCP_CACHE": "true", "YF_MCP_CACHE_DIR": "unused"}
    )
    assert cache.cache_enabled
