# Containers

The image, and the places it runs in, each in a folder of its own.

```
containers/
  images/
    yahoo-finance-mcp/
      Dockerfile          # what CI builds and publishes, build context: the repository root
  production/             # in operation, the published image, no clone needed
    compose.yaml          #   the server on 127.0.0.1, version from .env
    .env.example          #   template of .env: the version, the port, the token
  development/            # for development, built from this checkout
    compose.yaml          #   the server on 127.0.0.1:8001
```

| Folder | For | Image |
|---|---|---|
| `production/` | running the server, without a clone of the repository | from the GitHub container registry, the version named in `.env` |
| `development/` | trying a change in a container | built from this repository |

Both compose files keep the port on the loopback address, run the container
with a read-only root file system, no capabilities and `no-new-privileges`,
and cap the log Docker keeps at 5 files of 10 MB. CI checks the port and that
both files are valid. Their project names differ, so the two can run side by
side, each with a cache volume of its own.

## In operation

Into an empty folder, from the repository at `main`:

```sh
mkdir yahoo-finance-mcp && cd yahoo-finance-mcp
for file in compose.yaml .env.example; do
  curl -fsSL -o "$file" "https://raw.githubusercontent.com/benethos-hub/yahoo-finance-mcp/main/containers/production/$file"
done
cp .env.example .env && chmod 600 .env      # then edit it
docker compose up -d
```

The server is then at `http://localhost:8000/mcp`. To update, set
`YAHOO_FINANCE_MCP_VERSION` in `.env` to the new version, then
`docker compose pull && docker compose up -d`.

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
The 0.7 line is pushed under that name as well, the same image with the same
digest, and 0.8.0 is the first release without it. Switch to the new name
before then.

Built from the repository root:

```sh
docker build -f containers/images/yahoo-finance-mcp/Dockerfile -t benethos-yahoo-finance-mcp:local .
```

The [README](../README.md#docker) has the settings, `docker run` and the
details of the image.
