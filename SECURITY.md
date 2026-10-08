# Security

This server only reads market data. It holds no account, places no order and
authenticates to no data provider. What it does guard is itself: an HTTP port
that should answer only the clients meant to use it, an optional bearer token,
a result cache on disk and a container that runs with as few rights as it
can. Reports of weaknesses in any of that are welcome.

## Reporting a vulnerability

Please do **not** open a public issue. Report it privately through GitHub: on
this repository, **Security → Report a vulnerability**
(<https://github.com/benethos-hub/yahoo-finance-mcp/security/advisories/new>).

Helpful in a report:

- what an attacker can reach or do, and from where (the network, a browser
  on the host, a tool argument, the container)
- the steps or a request that shows it, and the version or commit
- no real tokens or secrets: redact them

Please give time for a fix before publishing details. The advisory can name
you, if you like.

## Versions

Fixes go into the latest minor line and `main` only. Older lines do not get
them, so the newest release of the current minor is the one to run.

## What counts

For example: reaching a tool over HTTP without the bearer token when one is
set, getting past the `Host` allow-list that guards against DNS rebinding,
the token or a URL's query string in the log or in a response, a tool
argument that makes the server reach a host other than Yahoo's or write
outside its cache directory, a crash or a hang that one request can cause,
and anything that undoes the container's hardening (non-root user, read-only
root file system, no capabilities).

Not in scope: the availability, accuracy or terms of Yahoo's own endpoints,
which this project does not control (see the disclaimer in the README), and
a port published beyond the loopback address without a token, which the
documentation advises against. Text that Yahoo returns, such as news
headlines, reaches the model as data. That it can say anything is known, a
way for it to make the server itself act differently is a finding.

How the HTTP transport, the bearer guard and the log are built is described
in [SPECS.md](SPECS.md), section 4.
