# Containers

The image, and the places it runs in, each in a folder of its own.

```
containers/
  images/
    yahoo-finance-mcp/
      Dockerfile          # what CI builds and publishes, build context: the repository root
  production/             # in operation, the published image, no clone needed
    compose.yaml          #   the server on 127.0.0.1, version from .env, Caddy with the profile https
    Caddyfile             #   Caddy's configuration: domain, certificate, 401 without a token
    .env.example          #   template of .env: the version, the port, the token, HTTPS
  development/            # for development, built from this checkout
    compose.yaml          #   the server on 127.0.0.1:8001
```

| Folder | For | Image |
|---|---|---|
| `production/` | running the server, without a clone of the repository | from the GitHub container registry, the version named in `.env` |
| `development/` | trying a change in a container | built from this repository |

Both compose files keep the server's port on the loopback address, run the
container with a read-only root file system, no capabilities and
`no-new-privileges`, and cap the log Docker keeps at 5 files of 10 MB. The
one service that answers beyond the loopback address is Caddy in
production, and only with the profile `https`. CI checks the ports and that
both files are valid. Their project names differ, so the two can run side by
side, each with a cache volume of its own.

## In operation

Into an empty folder, from the repository at `main`:

```sh
mkdir yahoo-finance-mcp && cd yahoo-finance-mcp
for file in compose.yaml Caddyfile .env.example; do
  curl -fsSL -o "$file" "https://raw.githubusercontent.com/benethos-hub/yahoo-finance-mcp/main/containers/production/$file"
done
cp .env.example .env && chmod 600 .env      # then edit it
docker compose up -d
```

The server is then at `http://localhost:8000/mcp`. To update, set
`YAHOO_FINANCE_MCP_VERSION` in `.env` to the new version, then
`docker compose pull && docker compose up -d`.

## With HTTPS

For clients on other machines, [Caddy](https://caddyserver.com/) stands in
front of the server. It answers on ports 80 and 443 of every address, takes
care of the certificate and forwards to the server over the compose network.
The server's own port stays on `127.0.0.1`. In `.env`:

```sh
COMPOSE_PROFILES=https
YAHOO_FINANCE_MCP_DOMAIN=mcp.example.com
YAHOO_FINANCE_MCP_TLS=acme
YF_MCP_BEARER_TOKEN=<long and random>
```

Then `docker compose up -d`, and clients use `https://mcp.example.com/mcp`
with `Authorization: Bearer <token>`. Port 80 redirects to HTTPS.

| `YAHOO_FINANCE_MCP_TLS` | Certificate | Needs |
|---|---|---|
| `acme` (default) | from Let's Encrypt or ZeroSSL, renewed by Caddy | the domain in public DNS pointing at this host, ports 80 and 443 reachable from the internet |
| `internal` | from Caddy's own CA, for a private network | clients that trust its root: `docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt .` |
| `files` | your own | `secrets/tls/cert.pem` and `secrets/tls/key.pem` in this folder, ignored by git |

The token is required with the profile, since the server is then reachable
from wherever this host is. Caddy answers a request without an
`Authorization` header with 401 itself, and the server checks the token of
every other. The domain is appended to `YF_MCP_ALLOWED_HOSTS` on its own,
without it the server would answer 421. Certificates and the ACME account
live in the volumes `caddy-data` and `caddy-config`, so a restart does not
ask the CA again. Caddy runs read-only like the server, without
capabilities except the one to bind ports 80 and 443. The image is
`caddy:2`, the major line, so `docker compose pull` brings Caddy's fixes
with the next start.

## For development

From `development/`:

```sh
docker compose up -d --build
```

The server is then at `http://localhost:8001/mcp`. An `.env` beside the file,
not versioned, is optional:

| Variable | Default | What it is |
|---|---|---|
| `YAHOO_FINANCE_MCP_PORT` | `8001` | the port on the host, on `127.0.0.1` |
| `YF_MCP_LOG_LEVEL` | `INFO` | the server's log level |
| `YF_MCP_*` | | anything else from the README's configuration table, the bearer token included |

## The image

`ghcr.io/benethos-hub/benethos-yahoo-finance-mcp`, for `linux/amd64` and
`linux/arm64`, built by `.github/workflows/publish.yml` with the same name and
version as the PyPI package. A release `v1.2.3` is tagged `1.2.3`, `1.2` and
`latest`. A run started by hand from `main` is tagged `edge`.

Up to 0.7.1 the image was named `ghcr.io/benethos-hub/yahoo-finance-mcp`.
Those releases, 0.4.0 to 0.7.1 with their minor-line tags, were copied to the
new name with the same digest, so every release is there. The 0.7 line was
pushed under the old name as well. Since 0.8.0 only the new name gets
releases.

Built from the repository root:

```sh
docker build -f containers/images/yahoo-finance-mcp/Dockerfile -t benethos-yahoo-finance-mcp:local .
```

The [README](../README.md#docker) has the settings, `docker run` and the
details of the image.
