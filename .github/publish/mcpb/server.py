"""Entry point of the Claude Desktop bundle: the console script, started by uv.

The manifest runs this file with ``uv run`` in the unpacked bundle, which
installs the project from its pyproject.toml and uv.lock first.
"""

from benethos_yahoo_finance_mcp.cli import main

if __name__ == "__main__":
    main()
