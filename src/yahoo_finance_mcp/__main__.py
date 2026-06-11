"""Enable ``python -m yahoo_finance_mcp`` as an alias for the server entry point."""

from __future__ import annotations

from .server import main

if __name__ == "__main__":
    main()
