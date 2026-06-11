# Open items

Pending tasks, mainly for publishing the project. Remove entries as they are
done.

## Before publishing to GitHub

- [ ] **Set the GitHub owner.** Replace the `<OWNER>` placeholder in
  [pyproject.toml](pyproject.toml) (`[project.urls]`) with the real GitHub
  username, e.g. `https://github.com/<OWNER>/yahoo-finance-mcp`.
- [ ] **Decide on the commit author email.** Current commits use
  `BeneODev <296451023+BeneODev@users.noreply.github.com>`. This becomes public in the
  commit history on push. Optionally switch to a GitHub noreply address
  (`<id>+<user>@users.noreply.github.com`). Nothing is pushed yet, so the two
  existing commits can still be rewritten if desired. If changed, also set the
  repo-local `git config user.email` so future commits match.
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
