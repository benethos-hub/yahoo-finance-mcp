# Releasing

A release is its own `release/X.Y.Z` branch and pull request. In this order:

1. **`uv lock --upgrade --dry-run` first.** Dependabot lifts direct
   dependencies only, and the transitive ones underneath move only when a
   direct bump happens to drag them along. An index installation (`uvx`,
   `pip`) resolves the newest of everything at install time, the container
   image freezes whatever `uv.lock` says, so a release is the moment the image
   catches up with what every index user already has. Refresh with
   `uv lock --upgrade` as its own commit, then the gates, plus the `yfinance`
   or `mcp` checks of [CLAUDE.md](../CLAUDE.md#verifying) for anything that
   sits under those. The refresh
   stays inside the patch windows (`~=` on `mcp`, `yfinance`, `pandas`,
   `pydantic`, `lxml` and `curl_cffi`) and so never shows a new minor or major
   of those. `uv tree --outdated --depth 1` does: it names the newest release
   on the index whatever the bound, and a `(latest: ...)` line after the
   refresh is such a release. A minor is taken by hand, on its own: checked like
   any `yfinance` or `mcp` bump, whichever of the six it is, and the window
   raised. A major is asked about first. A security hole
   does not wait for this step: Dependabot's security updates read the whole
   lockfile, transitive packages included, and arrive on their own. A fix past
   a window reaches nobody on the index until it is released, so it means a
   release at once.
   The same goes for everything else pinned here, and a release does not
   wait for Dependabot to propose any of it. The two images in the
   `Dockerfile` (`containers/images/yahoo-finance-mcp/`) move to the newest
   tag (a new uv release, say) and to the current digest of that tag, since
   a rebuild under the same tag, which is how the Debian fixes in the
   `python:3.X-slim` base arrive, gets no proposal at all. Every action
   pinned in `.github/workflows/` moves to its newest release, by its SHA.
   The build backend in `pyproject.toml`, `hatchling`, moves to its newest
   release by hand, like the image tags.
   Read the release notes of each, build the image for a Dockerfile change,
   and list every bump in the release PR.
   `mcp-publisher` and the bundle packer are pinned in the organisation's
   publishing actions and kept current there, not here.
2. Bump `version` in `pyproject.toml`, then `uv lock` and `uv sync --extra dev`
   (the packaging tests read the *installed* metadata). Let
   `tests/test_packaging.py` name every stale version example instead of
   hunting for them by eye, and `tests/test_server_json.py` the versions in
   `.github/publish/mcp-registry/server.json`, the MCP Registry entry,
   including the tag and file name in the bundle's download URL. Its
   `fileSha256` stays the placeholder of zeros, the release workflow writes
   the real hash.
3. Close `[Unreleased]` in `CHANGELOG.md` as `[X.Y.Z] - <date>` and add the
   compare links.
4. After the squash merge: annotated tag `vX.Y.Z`, push it, then
   `gh release create vX.Y.Z --verify-tag` with the changelog section as the
   notes. Publishing the release is what triggers `publish.yml`. Its first
   job, `ci-passed` (the organisation's `python-release-ci-passed`
   workflow), waits for the CI run the merge commit's push to main started
   and lets nothing be built unless that run succeeded, so a tag on a commit
   that never reached main, or on one whose CI is red, publishes nothing. It
   also audits `uv.lock` once more, and a waiver in `ignore-vulns` belongs
   there as well as in `ci.yml`. The uploads after it go through the
   organisation's `publish/` actions, and each stops first when the tag is
   not `v` plus the version in its own file: the wheel, `pyproject.toml`,
   `manifest.json` or `server.json`. A pre-release leaves `latest` where it
   is and is not listed in the registry. A manual run of `publish.yml` on
   main is a trial, and it is not part of a release: start it only when the
   maintainer asks for one, permission for the release does not cover it.
   `pypi-trial` builds and checks without uploading, and the image goes out
   as `edge`. The release PR's checks, main's CI on the merge commit and
   the `ci-passed` gate already stand between a tag and a broken upload.
5. **Check what shipped, not the build.** The three ghcr tags (`X.Y.Z`, `X.Y`,
   `latest`) of `benethos-yahoo-finance-mcp` must carry the same
   `org.opencontainers.image.revision` annotation, the versions *inside*
   the image must be what the lockfile says
   (`docker run --rm --entrypoint python <image> -c "import
   importlib.metadata as m; print(m.version('mcp'))"`), and PyPI's simple
   index with a cache-buster must list the version — the JSON API reports the
   old one for minutes after an upload. The MCP Registry must list it too:
   `https://registry.modelcontextprotocol.io/v0/servers?search=benethos-yahoo-finance-mcp`.
   Glama's Auto-Release builds and lists every GitHub release under the
   same version, with its notes, on the listing's releases page. Check that
   the version shows up there. Do not start "Build & Release" on Glama
   between releases: newer code would land under the version the server
   still reports.
