"""The pre-commit hook, run in a repository of its own in a temporary folder.

The hook in .githooks/ refuses staged files that hold a token, a key or
local state, and staged lines that look like a credential. Every line of
a credential here is put together from parts, so this file holds none of
them and passes the hook itself.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".githooks" / "pre-commit"
GIT = shutil.which("git")
ALLOW = "pragma: allowlist secret"


def _shell() -> str | None:
    """The shell git runs a hook with. Git for Windows brings its own,
    which is not on the path of every terminal."""
    found = shutil.which("sh")
    if found is None and GIT is not None:
        home = Path(GIT).resolve().parent.parent
        for place in ("bin/sh.exe", "usr/bin/sh.exe"):
            if (home / place).is_file():
                return str(home / place)
    return found


SH = _shell()

pytestmark = pytest.mark.skipif(
    SH is None or GIT is None, reason="the hook needs sh and git"
)

# One line per form the hook knows, each put together from parts.
CREDENTIALS = {
    "env-bare": "YF_MCP_BEARER_TOKEN" + "=Zq7xW2pL9mN4vB8kR5tY",
    "env-quoted": "YF_MCP_BEARER_TOKEN" + ' = "Zq7xW2pL9mN4vB8kR5tY"',
    "yaml": "bearer_token" + ": Zq7xW2pL9mN4vB8kR5tY",
    "json": '{"pass' + 'word": "Tr0ub4dor3xyzabc"}',
    "header": "Authorization: " + "Bearer " + "abcdefghijklmnop1234",
    "github": "token " + "ghp" + "_" + "abcdefghijklmnop1234",
    "github-pat": "github" + "_pat_" + "11ABCDEFG0abcdefghijklmnop",
    "pypi": "pypi" + "-AgEIcHlwaS5vcmc" + "A" * 50,
    "anthropic": "key " + "sk-" + "ant-api03-abcdefghijklmnop",
    "private-key": "-----" + "BEGIN " + "OPENSSH PRIVATE KEY-----",
}

# What names a secret without being one, as this repository writes it.
REFERENCES = [
    "YF_MCP_BEARER_TOKEN=",
    "# YF_MCP_BEARER_TOKEN=",
    "YF_MCP_BEARER_TOKEN=<long and random>",
    "YF_MCP_BEARER_TOKEN=...",
    'curl --header "Authorization: Bearer <token>"',
    "bearer_token = settings.bearer_token",
    "token = secrets.token_urlsafe(32)",
    'token = os.environ["YF_MCP_BEARER_TOKEN"]',
    "token: BearerToken",
    'field = "bearer_token"',
    "TLS_KEY_FILE: /run/secrets/tls.key",
    'ADD_KEYWORD = "add_keyword_long_value"',
]


def _git(repo: Path, *args: str) -> None:
    assert GIT is not None
    subprocess.run([GIT, *args], cwd=repo, check=True, capture_output=True)


def _hook(repo: Path) -> subprocess.CompletedProcess[str]:
    assert SH is not None
    return subprocess.run(
        [SH, HOOK.as_posix()],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    return tmp_path


def _stage(repo: Path, name: str, content: str = "x\n") -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    _git(repo, "add", "-f", name)


def test_the_hook_is_executable_in_the_repository() -> None:
    assert GIT is not None
    listed = subprocess.run(
        [GIT, "ls-files", "-s", ".githooks/pre-commit"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert listed.startswith("100755 "), listed


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.local",
        "containers/production/.env",
        "containers/development/.env.local",
        "containers/production/secrets/tls/cert.crt",
        "secrets/token",
        "cache.sqlite",
        "somewhere/results.sqlite-wal",
        "state.db",
        "server.pem",
        "containers/production/tls.key",
        "client.p12",
        ".claude/settings.local.json",
    ],
)
def test_refuses_files_that_never_belong(repo: Path, name: str) -> None:
    _stage(repo, name)

    answer = _hook(repo)

    assert answer.returncode == 1
    assert name in answer.stderr


@pytest.mark.parametrize(
    "name",
    [
        "containers/production/.env.example",
        "containers/production/compose.yaml",
        ".claude/settings.json",
        "src/benethos_yahoo_finance_mcp/settings.py",
        "tests/test_settings.py",
        "keys.md",
    ],
)
def test_lets_the_rest_pass(repo: Path, name: str) -> None:
    _stage(repo, name)

    assert _hook(repo).returncode == 0


@pytest.mark.parametrize("line", CREDENTIALS.values(), ids=CREDENTIALS.keys())
def test_refuses_a_line_that_looks_like_a_credential(repo: Path, line: str) -> None:
    _stage(repo, "notes.txt", line + "\n")

    answer = _hook(repo)

    assert answer.returncode == 1
    assert "credential" in answer.stderr


def test_shows_only_the_start_of_a_credential(repo: Path) -> None:
    _stage(repo, "notes.txt", CREDENTIALS["env-bare"] + "0123456789" * 5 + "\n")

    answer = _hook(repo)

    assert answer.returncode == 1
    assert "0123456789" * 3 not in answer.stderr


@pytest.mark.parametrize("line", REFERENCES)
def test_a_reference_to_a_secret_passes(repo: Path, line: str) -> None:
    _stage(repo, "notes.txt", line + "\n")

    answer = _hook(repo)

    assert answer.returncode == 0, answer.stderr


def test_an_allowlisted_line_passes(repo: Path) -> None:
    _stage(repo, "notes.txt", CREDENTIALS["env-bare"] + "  # " + ALLOW + "\n")

    assert _hook(repo).returncode == 0


def test_a_removed_line_is_not_looked_at(repo: Path) -> None:
    _stage(repo, "notes.txt", CREDENTIALS["env-bare"] + "\n")
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t.example",
        "commit",
        "-q",
        "--no-verify",
        "-m",
        "x",
    )
    _stage(repo, "notes.txt", "nothing\n")

    assert _hook(repo).returncode == 0


def test_nothing_staged_passes(repo: Path) -> None:
    assert _hook(repo).returncode == 0


def test_this_repository_passes(repo: Path) -> None:
    """Every tracked file staged at once: what is here now is no finding,
    so the hook stays quiet on an ordinary commit."""
    assert GIT is not None
    names = subprocess.run(
        [GIT, "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout.decode()
    for name in filter(None, names.split("\0")):
        source = ROOT / name
        if not source.is_file():
            continue
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    _git(repo, "add", "-A")

    answer = _hook(repo)

    assert answer.returncode == 0, answer.stderr
