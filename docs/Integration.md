# Integration Guide: using the personal CA from other apps and agents

This project exists so that nothing else on your machine — a Fileglancer app,
a dev server, an agent-driven test harness — has to mint its own throwaway,
self-signed TLS certificate. A one-off self-signed cert is never trusted by a
browser or HTTP client, so every consumer either fails closed or has to
disable certificate verification (`curl -k`, `verify=False`, `rejectUnauthorized:
false`, `NODE_TLS_REJECT_UNAUTHORIZED=0`, ...) to work around it. That's the
exact problem this tool avoids: `pca init` installs **one** root CA into your
local trust store(s) a single time, and every cert `pca issue` produces after
that is already trusted — no verification flags to disable, no CORS/`fetch`
failures from an untrusted cert.

The rule for any integration below is the same: **issue once per stable
identity, reuse forever** — call `pca issue --name <stable-name>` every time
you're about to start the thing that needs a cert, not just the first time.
It's idempotent (see "Idempotency" below), so this is cheap and keeps the
cert renewed automatically without any separate cron/reminder logic.

## Prerequisites

Someone (a person, or the first app/agent to need TLS) must have run `pca
init` once on the host. This creates the root CA under
`~/.local/share/personal-certificate-authority/mkcert/` and installs it into
whatever local trust stores `mkcert` can reach (system store, Firefox/Chrome
NSS db). If the host is headless/remote and `sudo` isn't available, `pca
init` still creates a working CA — it just can't fully self-install trust,
so also run `pca trust` (or visit `pca serve`) once from a real browser
session to finish trusting it there. See the main [README](../README.md).

All state lives under one directory, `$XDG_DATA_HOME/personal-certificate-authority`
(default `~/.local/share/personal-certificate-authority`), which on Janelia's
shared/NFS home directories is the same across compute nodes — a cert issued
while a job ran on one node is still there (and still trusted) when the same
named job runs on a different node later.

### Getting `pca` itself onto `PATH`

This project isn't published to PyPI or conda-forge, but it can still be
installed globally with:

```bash
pixi global install --git https://github.com/JaneliaSciComp/personal-certificate-authority
# or, from a local clone:
pixi global install --path ~/src/personal-certificate-authority
```

This builds a real (local, unpublished) conda package via
[`pixi-build-python`](https://pixi.prefix.dev/latest/build/backends/pixi-build-python/)
— an opt-in preview feature (`preview = ["pixi-build"]` in
`[tool.pixi.workspace]`), which is why this needed a dedicated
`[tool.pixi.package]` section rather than working automatically off the
plain hatchling/pip packaging above. It pulls in `mkcert` and every Python
runtime dependency as part of the same isolated global environment and
exposes `pca` on `~/.pixi/bin` — verified live: `pca init`/`pca
issue`/`pca status` all work correctly from a totally fresh global install,
with no separate `pixi run`/wrapper script needed. `~/.pixi/bin` needs to be
on `PATH`, which `pixi-completion`/`pixi init`'s shell setup already does
for most users.

If you'd rather not touch your global pixi environment, the fallback is a
one-line wrapper script that delegates to `pixi run --manifest-path` against
a clone of this repo instead:

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/pca <<'EOF'
#!/usr/bin/env bash
exec pixi run --manifest-path "$HOME/src/personal-certificate-authority" pca "$@"
EOF
chmod +x ~/.local/bin/pca
```

## For other Fileglancer apps (or any local service)

1. **Pick one stable `--name`** for the service — typically the app's own
   name (`fileglancer`, `my-viewer`, etc.), not something that changes per
   run/job/PID. The name is just a directory key under `certs/<name>/`; reuse
   it every time so you get the same cert file paths and a long-lived,
   idempotently-renewed certificate instead of a new one each start.

2. **Issue the cert before starting your server**, every time, as part of
   your own startup path — don't assume a human ran this ahead of time:

   ```bash
   pixi run --manifest-path ~/src/personal-certificate-authority pca issue \
     --name fileglancer --san localhost --san "$(hostname)"
   ```

   (If `pca` is on `PATH` in your own environment instead, just `pca issue
   ...` directly.) This prints the cert/key paths, or you can compute them
   yourself:

   ```
   ~/.local/share/personal-certificate-authority/certs/<name>/cert.pem
   ~/.local/share/personal-certificate-authority/certs/<name>/key.pem
   ```

3. **Point your server's TLS flags at those files.** For Fileglancer itself:

   ```bash
   pixi run uvicorn fileglancer.server:app \
     --host 0.0.0.0 --port 7878 \
     --ssl-keyfile ~/.local/share/personal-certificate-authority/certs/fileglancer/key.pem \
     --ssl-certfile ~/.local/share/personal-certificate-authority/certs/fileglancer/cert.pem
   ```

   This replaces `fileglancer`'s existing `/opt/certs/cert.{key,crt}`
   convention with a per-user cert that doesn't require an org PKI hand-off —
   use whichever fits your deployment (org PKI in production, this personal
   CA for local/dev use).

4. **If a client of your app needs to verify the connection** (another
   script, a health check, an agent — see below), have it trust the root CA
   explicitly rather than skipping verification:

   ```bash
   export SSL_CERT_FILE=~/.local/share/personal-certificate-authority/mkcert/rootCA.pem
   export REQUESTS_CA_BUNDLE=$SSL_CERT_FILE   # Python requests
   export NODE_EXTRA_CA_CERTS=$SSL_CERT_FILE  # Node.js
   ```

   or pass it directly, e.g. `httpx.Client(verify=SSL_CERT_FILE)` /
   `requests.get(url, verify=SSL_CERT_FILE)`.

If the app terminates TLS via [Caddy](https://caddyserver.com/) as a local
reverse proxy instead of directly (e.g. fronting a backend with no TLS
support of its own, like a notebook server or a web terminal), see
[`CaddyIntegration.md`](CaddyIntegration.md) for that specific pattern
instead of steps 2–3 above.

### As a Fileglancer App

This repo ships a [`runnables.yaml`](../runnables.yaml), so it can be added
to Fileglancer directly as an App (its own compute job) rather than run from
a shell: `Initialize Root CA`, `Issue Certificate`, `Renew Certificate`,
`Revoke Certificate`, and a long-running `Certificate Authority Web UI`
service (the `pca serve` download/trust-instructions page from the main
README) are all exposed as entry points. Other Fileglancer Apps don't need
to launch this repo at all to *use* a cert, though — they only need the `pca`
CLI available (via the `pixi` requirement) and to call `pca issue` as shown
above; the CA/cert files are shared host state, not something scoped to a
single job run.

## Relationship to Fileglancer's built-in HTTPS service proxy (PR #440, #445)

Fileglancer has its own HTTPS mechanism for the App services *it* launches
and proxies — see `docs/ServiceProxy.md` in the `fileglancer` repo (merged in
[PR #440](https://github.com/JaneliaSciComp/fileglancer/pull/440)). It's easy
to mix these up because both are "how do I get HTTPS for something local,"
but the difference that actually matters is **how much of the connection is
encrypted**, not just who issued the cert:

- **PR #440's proxy encrypts one hop: browser → nginx.** nginx terminates TLS
  at the edge with **one org-provided wildcard certificate** for a dedicated
  subdomain zone (e.g. `*.services.example.org`), then talks **plain HTTP**
  to the job's actual port on the compute node (`proxy_pass
  http://$upstream`). Identity/anti-enumeration comes from a signed hostname
  label and a per-job `${FG_SERVICE_TOKEN}`, not from the TLS layer. This is
  the right (and only practical) choice when a cert has to be trusted by
  *every* user of a shared, multi-user `fileglancer-hub` deployment — only an
  org/public CA can do that; a personal CA is trusted by exactly the one
  person who ran `pca init`.
- **This project encrypts every hop, end-to-end, to the process itself.**
  A `pca`-issued cert is terminated by the app (`--ssl-keyfile`/
  `--ssl-certfile`), so there's no plaintext leg anywhere — including on the
  internal network between the reverse proxy and the compute node, which
  PR #440's design explicitly does not protect. The tradeoff is the trust
  scope: whoever's browser connects has to trust that specific personal CA.

So for a Fileglancer-launched job **service** specifically, the two aren't
just alternatives, they're currently **mutually exclusive by construction**:
`auto_url` always publishes a hardcoded `http://$FG_HOSTNAME:$FG_SERVICE_PORT`
URL, and once a service publishes any URL, the job-detail endpoint rewrites
it to the proxied `https://job-<id>-<mac>.<zone>/...` form whenever
`apps.service_proxy_domain` is configured — unconditionally, with no way for
an entry point to say "don't, I'm already terminating my own TLS." Fixing
that is exactly what
[PR #445](https://github.com/JaneliaSciComp/fileglancer/pull/445) ("Let a
service opt out of the HTTPS proxy," open, not yet merged as of this
writing) adds: a `service_proxy: false` field on the entry point. When set,
Fileglancer publishes the job's raw `service_url` unchanged and
`/api/apps/resolve` refuses to proxy that job's hostname at all — so an app
that opted out is never routed through nginx's plaintext-backend path, even
by someone who has the signed label.

**Once PR #445 lands, a Fileglancer App service can get genuine end-to-end
TLS via this personal CA even on an instance where the org proxy is
enabled**, by combining:

```yaml
- id: my-service
  type: service
  service_proxy: false   # opt out of PR #440's rewrite (needs PR #445)
  auto_url: false         # self-publish, rather than the hardcoded http:// URL
  command: >
    pca issue --name my-service --san $FG_HOSTNAME &&
    my-app --host 0.0.0.0 --port $FG_SERVICE_PORT
      --ssl-certfile ~/.local/share/personal-certificate-authority/certs/my-service/cert.pem
      --ssl-keyfile ~/.local/share/personal-certificate-authority/certs/my-service/key.pem &
    echo "https://$FG_HOSTNAME:$FG_SERVICE_PORT" > "$SERVICE_URL_PATH"
    wait
```

Until PR #445 merges, this combination isn't available on an instance where
`apps.service_proxy_domain` is set — the proxy rewrite would still clobber
the self-published `https://` URL and try to reach a TLS-terminating backend
over plain HTTP, which fails outright. On an instance that doesn't set
`apps.service_proxy_domain` at all (no org proxy configured), this pattern
already works today, since there's no rewrite to opt out of.

**Rule of thumb:**
- Shared multi-user instance, org proxy enabled, service doesn't need
  end-to-end encryption to the backend → let PR #440's proxy handle it,
  don't issue it a `pca` cert too.
- Need real end-to-end encryption to the backend process (sensitive data,
  an untrusted internal network segment, compliance requirements) → use
  `pca issue` and terminate TLS in the app itself; on an instance with the
  org proxy enabled, that requires `service_proxy: false` (PR #445) once
  available.
- Anything not going through Fileglancer's App/job system at all —
  Fileglancer's own main server, a standalone local/dev service, an agent's
  throwaway dev server — always just use `pca issue` directly; none of this
  proxy machinery is involved.

This also means this repo's own `serve` entry point in `runnables.yaml`
deliberately serves **plain HTTP** and leaves `service_proxy`/`auto_url` at
their defaults: it has no sensitive backend traffic to protect (it only
*distributes* the CA cert — TLS on itself would be circular), so it's happy
to let PR #440's proxy add HTTPS at the edge for free when one is configured,
or be reached directly over plain HTTP when it isn't. No conflict either
way.

## For agents (Claude Code, scripts, automated test harnesses)

Agents that spin up a local HTTPS server — to test a webhook, preview a
change, or drive a browser against a dev build — very commonly reach for a
one-off self-signed cert (`openssl req -x509 -newkey ... -nodes`) generated
fresh every run. That pattern has two costs that compound the more an agent
does it:

- The cert is never trusted, so every verification step in the same task has
  to special-case it (`-k`, `verify=False`, etc.), which is easy to
  copy-paste forward into contexts where skipping verification is *not*
  fine.
- A new CA/cert per run means no continuity — nothing else on the machine
  (a browser tab left open, a second agent, a human checking the same URL
  later) shares that trust.

Use this tool instead: agents should call `pca issue` with a **stable name
derived from the task's purpose** (not a random/per-invocation ID), exactly
like any other app:

```bash
pca issue --name my-project-devserver --san localhost --san 127.0.0.1
```

Then start the server with `--ssl-keyfile`/`--ssl-certfile` pointed at the
resulting files, and verify against it (in the same or a follow-up step)
using `--cacert ~/.local/share/personal-certificate-authority/mkcert/rootCA.pem`
(curl) or the `SSL_CERT_FILE`/`verify=` mechanisms above — never
`-k`/`verify=False`. Because `pca issue` is idempotent (see below), calling
it at the start of every agent run is the correct default, not something to
special-case behind "if cert doesn't already exist" logic.

If `pca init` hasn't been run yet on the host, an agent should either run it
(`pca init`) or clearly surface to the user that TLS trust needs to be set
up once — it should not fall back to minting its own throwaway CA/cert as a
workaround.

## Idempotency

- `pca init` is safe to call repeatedly; it only regenerates the root CA
  (invalidating every previously issued cert) if you pass `--force`.
- `pca issue --name X ...` reuses the existing certificate for `X` as long as
  it already covers the requested SANs and isn't within 7 days of expiring;
  otherwise it reissues automatically. Pass `--force` to reissue
  unconditionally (e.g. after adding a SAN you expect to already be covered
  but isn't).

This means "issue on every startup" is the right integration pattern for
both apps and agents — it's a fast no-op in the common case, and it
self-heals expiry without any separate renewal job.
