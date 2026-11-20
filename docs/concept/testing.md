# Concept: testing

Part of the [concept](../CONCEPT.md): section 10.

## 10. Testing

- Unit tests mock `yfinance` and run **offline**, covering the yahoo
  functions and error normalization (`tests/yahoo/`, one file per yahoo
  module, `test_tickers.py` included, plus the cross-module
  `test_empty_answers.py`), formatting, the cache, settings, CLI/transport
  selection, the log lines and how they look, tool registration/schema,
  end-to-end tool invocation via `mcp.call_tool`, and `server_status` as a
  client calls it, with Yahoo refused (`test_formatting.py`,
  `test_cache.py`, `test_settings.py`, `test_cli.py`, `test_logbook.py`,
  `test_logbook_formats.py`, `test_server.py`, `test_tools_integration.py`,
  `test_status.py`, `test_transport.py`), and the prompts: every tool and
  field a recipe names, their arguments, a pasted bank export, and no share
  count in any log record (`test_prompts.py`). Three guard the shape of
  the code: `test_layers.py` the import table in both directions, that every
  library is imported in its one home and that only `settings.py` reads the
  environment (`NO_COLOR` excepted), `test_logbook_catalog.py` that every
  line is a logbook function, and `test_cache.py` that every cached category
  has a default TTL and a row in §8a. Six more guard what ships rather than
  what runs: `test_packaging.py` on the PEP 561 marker, the version
  examples, the supported Pythons and the layout block in CLAUDE.md (every
  path in it exists, every module is named there or here),
  `test_readme.py` on link targets PyPI
  cannot resolve, on every `#anchor` link landing on a heading, on the table
  of contents naming every section in order and on the tool list matching
  the registry, `test_docs.py` on every document a person reads here, the
  changelog excepted (each link and anchor leads somewhere, a document in
  `docs/` is named in capitals, each part of the concept names its document
  and leads back, and the overview lists every part with its sections, each
  number once), `test_server_json.py` on the MCP Registry
  entry, `test_mcpb.py` on the Claude Desktop bundle, and
  `test_publish_workflow.py` on the release workflow's wiring: which job
  calls which of the organisation's actions, with what, on which event and
  after what. `test_freshness.py` holds the daily check's wiring: its
  triggers, the organisation's job and workflow it calls and with what.
  `test_codeql.py` holds the two CodeQL calls to one organisation's
  workflow, the languages, the weekly schedule and the one permission, and
  `test_dockerfile_lint.py` the Dockerfile lint's pattern and registries.
- **The daily check.** `.github/workflows/freshness.yml` calls the
  organisation's reusable `freshness.yml` (`docs/freshness.md` in
  `benethos-hub/.github`) and adds one job of its own, the form that document
  calls "a job of the repository". It runs on a schedule, by hand, and once more
  after each completed run of `publish.yml`, so the `index` job below sees a
  release that does not install within minutes. The organisation's part keeps
  the issue "Pinned versions have newer releases": every pin of `uv.lock` with a
  newer release, within the patch windows and beyond, the build backend, known
  vulnerabilities, the images of the Dockerfile and the compose files, and the
  actions pinned by commit. Two jobs ask whether what a user gets today still
  works, and address the alarm issue "Newest dependency versions break the
  server", which the organisation's report keeps through `alarm-title`. The job
  `newest`, the organisation's `python/freshness-newest` action run from this
  workflow, runs the smoke test on the versions in `uv.lock`, then the tests and
  the smoke test on the newest versions `pyproject.toml` allows, which is what
  the auto-update extension and `uvx` resolve, and leaves the artifact
  `freshness-newest`. The job `index` of the organisation's workflow installs
  the published release from PyPI into a fresh environment, the path the
  auto-update extension takes, and runs the smoke test with its interpreter, so
  a bound that is not released yet or an installation that does not resolve
  shows there. Both say in one sentence what passed, which the pins issue lists
  under Checks. A run that proves nothing is `inconclusive` and leaves the alarm
  issue as it was: Yahoo refused the locked versions too, rate-limited the run
  (exit code 3 of `smoke.py`), or a step failed while nothing moved. The report
  then says so in the pins issue. It sits beside Dependabot, which writes the
  pull requests. Neither issue is a required check, and a pull request runs
  neither.
- `tests/smoke.py` is an ad-hoc **live** check against Yahoo, and it is not part of
  the pytest suite (no `test_*` functions, so it is not collected). It exits
  with 1 when a section or one of its lists comes back empty and with 3 when
  Yahoo rate-limits the run, which `test_smoke.py` holds.
- Quality gates: ruff (lint + format), mypy (type check), and a coverage floor
  of 80% (the badge in the README shows the current figure).
- **What the gates cannot see.** The suite mocks yfinance and stops at
  the yahoo package, so a behaviour change in either boundary passes every gate. For
  `yfinance` the answer is `tests/smoke.py` run before and after a bump, with a
  baseline to compare against. For `mcp` it is `tests/test_tools_integration.py`,
  which travels through `mcp.call_tool` and asserts a `ToolError`'s message
  arrives, since 2.1.0 dropped exactly that while 246 tests stayed green.
- CI (GitHub Actions): a `lint` job (ruff + mypy), a `test` matrix running
  `pytest` on Python 3.11-3.15, where only 3.15, the newest, measures
  coverage and enforces the floor, a `docker` job that builds the
  image for amd64 and arm64, smoke-tests that the container serves HTTP and
  passes its health check, lists every tool of the bundle manifest over
  stdio without a network or settings, the way directories such as Glama
  introspect a server, and checks both compose files, production with
  its profile `https` (valid, every port on the loopback address except
  Caddy's 443, read-only root, development builds and production
  pulls), and a `fresh-install`
  job. The first three install from `uv.lock` (`uv sync --frozen`) for
  reproducibility. `fresh-install` deliberately does **not**: it builds the
  wheel and installs it into a clean environment with no lockfile, then imports
  the package, lists the tools and runs the entry point. That is the path a user
  takes, and a lockfile hides breakage in the *declared* dependency ranges —
  0.3.0 shipped an unbounded `mcp` requirement, resolved to an incompatible major
  on a fresh install and failed at import while every other job stayed green.
  Since 0.12.0 the six dependencies that decide what an answer looks like
  (`mcp`, `yfinance`, `pandas`, `pydantic`, `lxml`, `curl_cffi`) are declared
  with `~=`, a patch window: an index installation and the auto-update
  extension take their patches on their own, a minor waits until it was
  checked here and the window raised ([RELEASING](../RELEASING.md)). The two times a
  dependency hurt this server, mcp 2.1.0 and pandas 3.1.0, it was a minor.
  A `lowest-versions` job checks the other end of those ranges: it installs
  every direct dependency at its lower bound (`--resolution lowest-direct`)
  on Python 3.11, again without the lockfile, runs the suite and audits
  those versions for known vulnerabilities. An `audit` job checks every
  version in `uv.lock`, for every platform and Python version, against PyPI
  and OSV, since GitHub's dependency graph does not read `uv.lock`. Like
  every other job both are required checks on `main`, so a red run blocks
  the merge until the lower bound in `pyproject.toml` it names is raised or
  the locked version is fixed.
- `brand`, `lint`, `test`, `lowest-versions`, `audit` and `codeql` call the
  reusable workflows of the benethos-hub organisation (`benethos-hub/.github`,
  followed at `main`), shared by its Python projects. `brand` checks that
  `assets/brand/icon.svg` and the 512×512 `icon.png` and 1280×640
  `social-preview.png` exported from it are present and not older than the
  SVG. Their checks are named `<job> / <name>`, such as `test / Python 3.15`.
  `fresh-install` and `docker` are this project's own. `dockerfile-lint`,
  the organisation's as well, runs hadolint over `containers/**/Dockerfile`, with `docker.io` and
  `ghcr.io` as the registries a `FROM` may pull from, and files its findings
  under Security, Code scanning as well, and its job stays green on them,
  like `codeql`. What turns red on a new finding is the check GitHub adds to
  a pull request per tool, `Code scanning results / <tool>`, and the
  threshold for that is one setting of the repository for every scanner
  (Settings, Code security, Code scanning, Protection rules, Check failure:
  security alerts High or higher, other alerts Errors and warnings, as the
  organisation's `repository-settings.md` says). Neither scanner job is a
  required check. The test `test_dockerfile_lint.py` holds the pattern to
  every Dockerfile of the repository and the trusted registries to every
  `FROM`. `codeql` runs CodeQL
  on the Python code and on the workflows with the `security-and-quality`
  suite: the security queries GitHub's default setup of code scanning ran
  before, and the maintainability and reliability queries that setup does
  not offer, such as an unreachable branch, a comparison that is always true
  or an unused import. The findings go to Security, Code scanning, as
  warnings and notes. A finding never fails the job, so its check
  `codeql / CodeQL` is no required check, by decision: it reports, the
  Security tab holds the result. `.github/workflows/codeql.yml` runs the same
  call every Monday at 05:00 UTC, half an hour after the freshness run so the
  two do not fall together, and by hand, so a query GitHub adds later reads
  code nobody changed, under the same category, so each run refreshes the
  last. The default setup had to be switched off first, since GitHub
  rejects a workflow's upload for a language the default setup analyses. A
  rule that never applies here would go into a CodeQL configuration file as
  a `query-filters` entry with its reason, named by `config-file`. There is
  none so far. The organisation's workflows and actions followed at `main`
  pass `actions/unpinned-tag` because the organisation's action names its
  owner as trusted, through a model pack it writes into the checkout before
  the analysis (`trusted-owners` in its `docs/codeql.md`), so no file here
  does. `test_codeql.py` holds every other action to a commit SHA, offline
  and before any run. A
  finding that is wrong in one place is dismissed in the Security tab with
  its reason, so that a new one stands out. A `coverage-badge`
  job, the organisation's as well, runs on a push to `main` only and
  commits the coverage `test / Python 3.15` measured as `coverage.json` to
  the `badges` branch, which the README's coverage badge reads. It is no
  required check, since a pull request does not run it.
- Every third-party action in the four workflows is pinned to a full commit
  SHA, with the version it stands for in a trailing comment, and the two
  base images in the
  `Dockerfile` (`containers/images/yahoo-finance-mcp/`) by digest next to
  their tag. A tag is a pointer its owner can
  move, and the publish workflow holds the credentials that push to PyPI and
  ghcr. Dependabot reads the comment and raises SHA and comment together.
  Caddy in the production compose file is the deliberate exception: `caddy:2`
  follows its major line. It is a server facing the internet that someone
  else runs, so `docker compose pull` should bring its security fixes the
  day they ship rather than with the next release here, and Caddy keeps its
  configuration compatible within a major version. Nothing is built from
  it, so no credentials depend on it. Dependabot reads the tag all the same
  and proposes the next line, `caddy:3`, when it comes out. The organisation's workflows and
  actions in `benethos-hub/.github` are the other exception, followed at
  `main`, and they pin the actions they use themselves.
- Dependabot covers GitHub Actions, the two images in the `Dockerfile`,
  Caddy's tag in the production compose file and, since 0.5.1, the Python
  dependencies in `uv.lock`. In the `Dockerfile` it reads `FROM` lines
  only, so the uv image is a stage of its own rather than a `COPY --from=`
  reference, and pinned to its patch, since Dependabot proposes only tags of
  the precision already written. The server's own image in the production
  compose file takes its version from `.env`, and the development compose
  file builds from the checkout, so neither has a tag to raise. The ecosystem for the Python dependencies
  is `uv`, since `pip` does not read `uv.lock`. It only proposes **direct**
  dependencies, and transitive ones move only when a direct bump drags them
  along, so a periodic `uv lock --upgrade` remains the way to refresh the
  rest. The moment for it is **before every version bump**, as the first
  step of [RELEASING](../RELEASING.md), and a release takes every newer
  version on offer rather than waiting for a proposal: an image that ships
  the direct bumps without the transitive ones underneath is half a rebuild.
  Minor and patch updates arrive grouped, one pull request per ecosystem and
  week, a major on its own, and the six dependencies with a patch window
  (`mcp`, `yfinance`, `pandas`, `pydantic`, `lxml`, `curl_cffi`) always on
  their own, since each needs the checks CLAUDE.md describes, and the pull
  request of a release past a window is where the window is lifted. The
  `versioning-strategy` is `increase-if-necessary`: a release the window
  allows changes `uv.lock` alone, and one past it moves the window, as `~=`
  again. Left to itself Dependabot takes this project for a library, since
  its description matches PyPI, and widens `~=` to a range over two minors,
  which is no patch window any more.
- A separate `publish` workflow runs when a GitHub release is published.
  Every upload in it goes through an action of the organisation
  (`benethos-hub/.github`, `actions/publish/`), while the jobs stay here,
  since PyPI and the MCP Registry trust the workflow of the job that
  uploads. Its first job, `ci-passed`, lets nothing be built until the CI
  run of the release commit on `main` has passed, and audits `uv.lock` once
  more. The upload jobs after it are independent of each other. It builds the sdist + wheel (`uv build`) and uploads
  them to **PyPI via Trusted Publishing (OIDC)**, and it builds the container
  image for `linux/amd64` and `linux/arm64` and pushes it to **ghcr.io** as
  `ghcr.io/benethos-hub/benethos-yahoo-finance-mcp`, authenticating with the
  automatic `GITHUB_TOKEN`. The image carries the distribution's name, and
  the PyPI job deploys to the environment `pypi-benethos-yahoo-finance-mcp`.
  The image's earlier name is in `containers/README.md`. Neither half stores
  a secret, and a failure
  in one does not withhold the other. Release tags become `X.Y.Z`, `X.Y` and `latest`, a
  pre-release its exact version only, so `latest` stays on the last full
  release. Every upload stops first when the tag is not `v` plus the
  version in its own file, the wheel, `pyproject.toml`, `manifest.json` or
  `server.json`, since PyPI would refuse the upload while the image job
  pushed its tags with the old code. The workflow can also be started by
  hand as a trial, which is not part of a release and runs only when the
  maintainer asks for it: it pushes the image as `edge`,
  from `main` only, and `pypi-trial` builds and checks the package and asks
  PyPI whether it would take it, without uploading and without the
  credentials of the upload job, because a version may only be uploaded
  there once. The image release reuses the layers the arm64 build in CI
  cached. Note that a
  ghcr package is private when first created and has to be made public by an
  organisation owner, which is also gated by an organisation-level setting. A
  public package is still absent from the repository sidebar for a logged-out
  visitor, because that block is fed by an API with no anonymous access. That is
  not a misconfiguration and there is no setting for it, so the README badge row
  carries the image link instead.
  A third job lists the release in the **MCP Registry**
  (registry.modelcontextprotocol.io) as
  `io.github.benethos-hub/benethos-yahoo-finance-mcp`, from
  `.github/publish/mcp-registry/server.json`. It runs after the three
  package jobs and skips a pre-release, since the registry checks every package when it takes the entry: the
  README of that version on PyPI must carry an `mcp-name:` line and the image
  config the `io.modelcontextprotocol.server.name` label, each naming the
  entry. It logs in with the workflow's OIDC token, which the registry trusts
  for the `io.github.benethos-hub/` namespace, so it stores no secret either.
  An entry cannot be changed once taken, and `tests/test_server_json.py`
  holds its version, description and name to the package before it goes
  out. Its image entry starts the container with `--transport stdio`, which
  a client launching it as a local process needs, and as hardened as the
  production compose file: `--read-only`, the same two tmpfs mounts,
  `--cap-drop ALL` and `no-new-privileges`, plus `--no-healthcheck`, since
  the image's check probes an HTTP port a stdio container never opens. A
  test holds the mounts to the compose file. The entry lists the Claude
  Desktop bundle as a third package (`registryType: "mcpb"`), by the
  download URL of this release's versioned asset, which is the only form the
  registry takes for a GitHub-hosted bundle. Its required `fileSha256`
  exists only once the release has built the bundle, so the committed entry
  holds zeros and the registry job, which waits for the bundle job too,
  downloads the attached file and writes its hash (the organisation's
  `publish/mcp-registry` action, which refuses another file name, another
  release and a hash already filled in). The registry takes an
  entry whole or not at all, so should it still refuse the one with the
  bundle after the retries, the action drops the bundle, publishes
  the rest so the version is listed with PyPI and the image, and fails
  anyway, which leaves the refusal in sight. The MCP list in VS Code's
  extension view does not show it: that list comes from GitHub's own
  registry, a selection of 394 servers on 2026-10-10 that held none of the
  official registry's Yahoo Finance servers, so a listing does not reach it
  on its own.
  A fourth job attaches a **Claude Desktop bundle** to the release,
  `benethos-yahoo-finance-mcp-X.Y.Z.mcpb`, which installs with a double
  click and no configuration file. The same file goes up a second time as
  `benethos-yahoo-finance-mcp.mcpb`, so
  `releases/latest/download/benethos-yahoo-finance-mcp.mcpb` always reaches
  the newest full release. It is a `uv` bundle (manifest 0.4): it
  carries `pyproject.toml`, `uv.lock` and the source, Claude Desktop starts
  `uv run --frozen` in the unpacked directory, and the dependencies are the
  locked ones, as in the image. `.github/publish/mcpb/build.py` stages it
  with the standard library alone, and the organisation's `publish/mcpb`
  action validates and packs it with the locked `mcpb` CLI and compares the
  packed file byte for byte with the staged tree.
  The manifest is committed as it ships, and `tests/test_mcpb.py` holds its
  version, metadata, tool list (each tool's first sentence) and prompts
  (each with its text as the server renders it, an argument written
  `${arguments.name}`) to the package. The two lists come from the server:
  `sync_manifest.py` beside `build.py` writes them and leaves every other
  field alone, and the test names that command while they differ. It sets
  `prompts_generated`, which turns off Claude Desktop's check of the prompts
  against their text (§7a), and `tools_generated`, so both bundles carry the
  same two flags. It asks for no settings. Tested on 2026-10-10
  in Claude Desktop twice, on a machine with uv installed and in a fresh
  Windows Sandbox without uv or Python: both ran, so Claude Desktop provides
  uv and Python
  itself, as the bundle format's documentation says, and a user needs
  nothing installed beforehand. The `mcpb` CLI 2.1.2 requires the
  `mcp_config` with the `uv` command even for a `uv` bundle, although the
  format calls it optional.
  The same job attaches a second bundle,
  `benethos-yahoo-finance-mcp-auto-update.mcpb` (and its copy with the
  version), through the same action. It carries no code, only the manifest,
  the icon and the license: Claude Desktop runs `uv tool run
  benethos-yahoo-finance-mcp`, the newest release on PyPI, with whatever
  dependency versions that release allows. `build.py --auto-update` makes its
  manifest from the pinned one, with its own name (Claude Desktop keys an
  extension by it, so the two stand side by side), display name, description
  and server, and `tests/test_mcpb.py` holds the rest equal. So it declares
  the same prompts, which Claude Desktop lists when installing, and sets
  `prompts_generated` and `tools_generated`: installed once, its manifest
  stays at the release that built it while the server moves on, and Claude
  Desktop refuses an undeclared prompt and checks a declared one against its
  text unless `prompts_generated` is set (§7a). Without it a later release
  with a new or changed recipe would be refused in every auto-update
  installation. 0.13.0 left the prompts out of this manifest, and Desktop's
  install dialog then listed none, while "+" offered all six. `tools_generated`
  lets the tools a later release adds through: a manifest that left a tool
  out and set it got the tool listed and its call answered (measured the
  same day). Without the flag that case was not measured, and Desktop logged
  no check of tools. The tool list stays for display. Tested on 2026-11-03
  in a Windows Sandbox without uv or Python: Claude Desktop
  downloaded uv 0.9.7 of its own, uv a Python 3.14, and the extension ran
  0.10.2. After 0.11.0 was published, restarts at 3 and at 9 minutes 49
  seconds after the last check still ran 0.10.2, the one at 12 minutes ran
  0.11.0: uv keeps PyPI's simple index for its `max-age` of 600 seconds.
  Offline, the command ran from the cache within those 10 minutes and failed
  after them (`Failed to fetch`, uv 0.9.7, measured the same day), so the
  extension needs PyPI to start once its last check is older. With
  Smart App Control on, Code Integrity blocked that downloaded `uv.exe`, for
  either bundle.
  One name is used throughout: the PyPI
  distribution, the import package (`benethos_yahoo_finance_mcp`, underscores
  because a module name cannot contain hyphens), the console script, and the
  MCP server identity are all `benethos-yahoo-finance-mcp`. Only the GitHub
  repository keeps the plain `yahoo-finance-mcp`, deliberately, for
  discoverability.
