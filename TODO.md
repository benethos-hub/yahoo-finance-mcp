# Open items

Pending tasks, mainly for publishing the project. Remove entries as they are
done.

## Deployment

- [x] Dockerfile that hosts the server over streamable-HTTP (built and verified).
- [x] `compose.yaml` for Docker Compose (built and verified).
- [ ] Optionally publish the image to a registry (e.g. `ghcr.io`) via a
  GitHub Actions workflow on release/tag.

## Optional polish (deferred — items 6-8 from the publishing review)

- [ ] `CONTRIBUTING.md` + issue / pull-request templates.
- [ ] README badges (CI status, Python version, license).
- [x] Concrete usage examples in the README ("Example prompts" section, grouped
  by tool). A full sample request/response transcript is still optional.

## Future features (see SPECS.md §11)

- [ ] Multi-symbol batch for `get_quote`.
- [x] Persistent caching with tiered TTLs — implemented as a result-level SQLite
  cache (`cache.py`), since `requests-cache` is not viable with yfinance's
  curl_cffi backend.
- [ ] Validate `period` / `interval` / `freq` against known value sets.
- [x] Configurable log level via environment variable (`YF_MCP_LOG_LEVEL`).
