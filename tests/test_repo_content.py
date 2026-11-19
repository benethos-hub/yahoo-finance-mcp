"""What never belongs in a versioned file, checked over every tracked file.

The pre-commit hook in .githooks/ looks at staged lines, and only where it
is enabled. This test reads the files git tracks, on every run of the
suite and so in CI, and fails on:

- an e-mail address on a domain not reserved for examples, as a person's
  own would be,
- a path of a machine or of a user, also in the form Git Bash and WSL
  write it,
- a credential in the forms the pre-commit hook knows: a token by its
  prefix, and a value given to a name such as ``*_TOKEN`` or ``password``.

A line that must show such a form ends with ``pragma: allowlist secret``,
as for the hook. The rules are in ``content_helpers.py``.
"""

from __future__ import annotations

import shutil
import subprocess
from functools import cache
from pathlib import Path

import pytest

from content_helpers import ALLOW, CREDENTIALS, REFERENCES, problems

ROOT = Path(__file__).resolve().parent.parent


@cache
def tracked() -> tuple[Path, ...]:
    """The files git tracks, as text. A binary file is left out."""
    git = shutil.which("git")
    if git is None:
        pytest.fail("the repository content is read through git, which is missing")
    done = subprocess.run(
        [git, "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False
    )
    if done.returncode != 0:
        pytest.fail("the repository content is read through git: not a git checkout")
    found = []
    for name in filter(None, done.stdout.decode().split("\0")):
        path = ROOT / name
        if path.is_file() and b"\0" not in path.read_bytes():
            found.append(path)
    return tuple(found)


def test_the_repository_holds_none_of_it() -> None:
    files = tracked()
    assert len(files) > 100, "git listed too few files to be this repository"
    hits = []
    for path in files:
        text = path.read_bytes().decode("utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            hits += [
                f"{path.relative_to(ROOT).as_posix()}:{number}: {problem}"
                for problem in problems(line)
            ]
    assert hits == [], "\n".join(hits)


# -- the rules themselves, on lines put together so the scan above does
# -- not find them in this file.

AT = "@"


@pytest.mark.parametrize(
    "line",
    [
        "someone" + AT + "provider.de",
        "Owner <someone" + AT + "provider.net>",
        "contact: first.last" + AT + "mail.provider.com",
        "rechnung" + AT + "müller.de",
    ],
)
def test_an_address_on_a_real_domain_is_found(line: str) -> None:
    assert problems(line)


@pytest.mark.parametrize(
    "line",
    [
        "someone" + AT + "example.com",
        "agent" + AT + "agents.test",
        "Co-Authored-By: Claude <noreply" + AT + "anthropic.com>",
        "1+someone" + AT + "users.noreply.github.com",
        AT + "pytest.mark.parametrize",
        "uses: actions/checkout" + AT + "v4.2.2",
        "ghcr.io/astral-sh/uv:0.13.9" + AT + "sha256:0123abcd",
    ],
)
def test_an_address_for_examples_passes(line: str) -> None:
    assert problems(line) == []


@pytest.mark.parametrize(
    "line",
    [
        "C:" + "\\Users\\someone\\project",
        "D:/" + "Users/someone/x",
        "/" + "Users/someone/project",
        "/" + "home/someone/.local",
        "sh /" + "mnt/d/projects/x/setup.sh",
        "/" + "c/Users/someone/project",
        "cd /" + "d/projects/yahoo-finance-mcp",
        "D:" + "\\projects\\yahoo-finance-mcp\\.venv",
        "d:" + "/projects/yahoo-finance-mcp",
    ],
)
def test_a_path_of_a_machine_is_found(line: str) -> None:
    assert problems(line)


@pytest.mark.parametrize(
    "line",
    [
        "containers/production/secrets/tls/cert.pem",
        "WORKDIR /" + "home/appuser",
        "--tmpfs /" + "home/appuser/.cache:uid=10001,gid=10001,mode=0700",
        "`C:" + "\\\\abs\\\\path\\\\to\\\\.venv\\\\Scripts\\\\python.exe`",
        r"C:\Program Files\Claude\claude.exe",
        "      - ./caddy.d:/etc/caddy/caddy.d:ro",
        r"re.compile(r'\d:\d')",
        "see https://example.org/home/page",
    ],
)
def test_a_path_inside_the_project_passes(line: str) -> None:
    assert problems(line) == []


@pytest.mark.parametrize("line", CREDENTIALS.values(), ids=CREDENTIALS.keys())
def test_a_credential_is_found(line: str) -> None:
    assert problems(line)


@pytest.mark.parametrize("line", REFERENCES)
def test_a_name_that_is_given_no_value_passes(line: str) -> None:
    assert problems(line) == []


def test_an_allowlisted_line_passes() -> None:
    line = next(iter(CREDENTIALS.values()))
    assert problems(line + "  # " + ALLOW) == []
