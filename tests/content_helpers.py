"""What never belongs in a versioned file, as rules for one line, and lines
that show each rule.

``test_repo_content.py`` holds every tracked file to the rules, and
``test_pre_commit.py`` holds the hook in ``.githooks/`` to the same lines
of credentials, so the two cannot drift apart. CREDENTIAL, NAMED and
REFERENCE follow the patterns of ``.githooks/pre-commit``. A change to one
changes the other.

The lines are put together here, so this file holds none of them."""

from __future__ import annotations

import re

ALLOW = "pragma: allowlist secret"

# Domains reserved for examples and tests (RFC 2606, RFC 6761), and the
# addresses a commit trailer names on purpose.
RESERVED_SUFFIXES = (".example", ".test", ".invalid", ".localhost")
RESERVED_DOMAINS = frozenset({"example.com", "example.org", "example.net"})
ALLOWED_ADDRESSES = frozenset({"noreply@anthropic.com"})
# The domain of GitHub's private commit addresses, as a whole.
NOREPLY_DOMAINS = frozenset({"users.noreply.github.com"})

# Something before the @, so a decorator such as @pytest.fixture is no
# address, and * for a pattern such as *@*.example. A domain may hold
# letters beyond ASCII.
ADDRESS = re.compile(
    r"(?<![A-Za-z0-9._%+*-])([A-Za-z0-9._%+*-]+)@"
    r"((?:(?:[^\W_]|[*-])+\.)+[^\W\d_]{2,})\b"
)
# A user's folder on Windows, macOS and Linux, a drive as WSL and Git Bash
# mount it, and any drive path but the programs' folders. A letter after a
# backslash is a regular expression, as \d:\d, and one after a dot the end
# of a name, as caddy.d:/etc. Two are this repository's own: the image's
# user appuser, and the placeholder C:\\abs\\path the README shows.
PATH = re.compile(
    r"[A-Za-z]:[\\/]+Users[\\/]|(?<![\w.])/Users/\w"
    r"|(?<![\w.])/home/(?!appuser\b)\w"
    r"|(?<![\w.])/mnt/[a-z]/"
    r"|(?<![\w.])/[A-Za-z]/(?:Users|home|projects)/\w"
    r"|(?<![\w\\.])[A-Za-z]:[\\/]+(?!Program Files|Windows\b|abs[\\/])\w"
)
CREDENTIAL = re.compile(
    # A bearer token as a client sends it, the tokens of GitHub and PyPI, a
    # key of the Anthropic API and a private key.
    r"Bearer [A-Za-z0-9._-]{16,}|gh[pousr]_[A-Za-z0-9]{16,}"
    r"|github_pat_[A-Za-z0-9_]{20,}|pypi-[A-Za-z0-9_-]{50,}"
    r"|sk-ant-[A-Za-z0-9_-]{16,}"
    r"|BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY"
    # A name that ends in TOKEN, SECRET, PASSWORD or _KEY, maybe with more
    # parts such as _ENV, then the value. _KEYWORD is no such name. A
    # value that starts with / is a path.
    r"|(?:TOKEN|SECRET|PASSWORD|_KEY)(?:_[A-Z]+)*\s*[:=]\s*[\"']?"
    r"[A-Za-z0-9+_-][A-Za-z0-9+/_.-]{11,}"
)
# The same in any case, as JSON and YAML write it: a quoted value, or a
# bare one that ends the line or a word. A bare value with a dot or a
# bracket is code, such as token = base64.b64encode(raw).
NAMED = re.compile(
    r"(?:^|[^a-z0-9])[\"']?[a-z0-9_]*(?:token|secret|password|passwd|_key)[\"']?"
    r"\s*[:=]\s*"
    r"(?:[\"'][A-Za-z0-9+_-][A-Za-z0-9+/_.-]{11,}"
    r"|[A-Za-z0-9+_-][A-Za-z0-9+/_-]{11,}(?:\s|$))",
    re.IGNORECASE,
)
# What such a name is given in code without being a value: the path of a
# *_FILE setting, a constant or the name of an environment variable, the
# name of a field in quotes, a type and an attribute.
REFERENCE = re.compile(
    r"_FILE[\"']?\s*[:=]"
    r"|[:=]\s*[\"']?[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$"
    r"|[:=]\s*[\"'][a-z]+(?:_[a-z]+)+$"
    r"|[:=]\s*[A-Z][a-z]+(?:[A-Z][a-z]+)+$"
    r"|[:=]\s*[a-z_]+(?:\.[a-z_]+)+$"
)


def _reserved(domain: str) -> bool:
    """Whether ``domain`` is reserved for examples, or names no domain of
    anyone: a placeholder such as ``*.domain`` or a whole top-level domain
    such as ``*.de``, one label after the wildcards."""
    domain = domain.lower()
    labels = [label for label in domain.split(".") if label != "*"]
    return (
        len(labels) < 2
        or domain in RESERVED_DOMAINS
        or domain.endswith(RESERVED_SUFFIXES)
    )


def addresses(line: str) -> list[str]:
    """The addresses of ``line`` on a domain not reserved for examples."""
    return [
        found.group(0)
        for found in ADDRESS.finditer(line)
        if not _reserved(found.group(2))
        and found.group(0).lower() not in ALLOWED_ADDRESSES
        and found.group(2).lower() not in NOREPLY_DOMAINS
    ]


def credentials(line: str) -> list[str]:
    """What in ``line`` looks like a credential, each cut to its start."""
    found = [m.group(0).rstrip() for m in CREDENTIAL.finditer(line)]
    found += [m.group(0).rstrip() for m in NAMED.finditer(line)]
    starts = [text[:12] for text in found if not REFERENCE.search(text)]
    return list(dict.fromkeys(starts))


def problems(line: str) -> list[str]:
    """What is wrong with one line, each named by its rule."""
    if ALLOW in line:
        return []
    found = [f"address {a}" for a in addresses(line)]
    found += [f"path {m.group(0)}" for m in PATH.finditer(line)]
    found += [f"credential {start}..." for start in credentials(line)]
    return found


# -- lines for both tests, split so no file of the repository holds one.

_RANDOM = "Zq7xW2pL9mN4vB8kR5tY"

# A credential, in the forms the rules know.
CREDENTIALS = {
    "env-bare": "YF_MCP_BEARER_TOKEN" + "=" + _RANDOM,
    "env-quoted": "YF_MCP_BEARER_TOKEN" + ' = "' + _RANDOM + '"',
    "yaml": "bearer_token" + ": " + _RANDOM,
    "json": '{"pass' + 'word": "Tr0ub4dor3xyzabc"}',
    "python-literal": "token = " + '"' + "hunter2-but-longer" + '"',
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
    'TOKEN_VAR = "YF_MCP_BEARER_TOKEN"',
    'curl --header "Authorization: Bearer <token>"',
    'headers={"Authorization": f"Bearer {token}"}',
    "bearer_token = settings.bearer_token",
    "token = secrets.token_urlsafe(32)",
    'token = os.environ.get("YF_MCP_BEARER_TOKEN")',
    "token: BearerToken",
    'field = "bearer_token"',
    "bearer_token: str | None = None",
    "TLS_KEY_FILE: /run/secrets/tls.key",
    'ADD_KEYWORD = "add_keyword_long_value"',
]
