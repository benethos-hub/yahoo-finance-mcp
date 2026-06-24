# Open items

Pending tasks, mainly for publishing the project. Remove entries as they are
done.

## Before publishing to GitHub

- [x] **Set the GitHub owner.** Project URLs point to
  `https://github.com/benethos-hub/yahoo-finance-mcp`.
- [x] **Decide on the commit author email.** History rewritten to
  `BeneODev <296451023+BeneODev@users.noreply.github.com>` (GitHub noreply); the
  repo-local `git config user.email` is set to match for future commits.
- [ ] **Create the remote and push** `main` (e.g. via `gh repo create` /
  `git remote add origin ...`).

## Deployment

- [x] Dockerfile that hosts the server over streamable-HTTP (built and verified).
- [x] `compose.yaml` for Docker Compose (built and verified).
- [ ] Optionally publish the image to a registry (e.g. `ghcr.io`) via a
  GitHub Actions workflow on release/tag.

## Optional polish (deferred — items 6-8 from the publishing review)

- [ ] `CONTRIBUTING.md` + issue / pull-request templates.
- [ ] README badges (CI status, Python version, license).
- [ ] A concrete usage example in the README (sample prompt + sample response).

## Future features (see SPECS.md §11)

- [ ] Multi-symbol batch for `get_quote`.
- [x] Persistent caching with tiered TTLs — implemented as a result-level SQLite
  cache (`cache.py`), since `requests-cache` is not viable with yfinance's
  curl_cffi backend.
- [ ] Validate `period` / `interval` / `freq` against known value sets.
- [x] Configurable log level via environment variable (`YF_MCP_LOG_LEVEL`).
