# Integrating with a Caddy-fronted app

Several Fileglancer-launched apps use [Caddy](https://caddyserver.com/) as a
local reverse proxy purely to terminate TLS in front of a backend that has
no TLS support of its own (e.g. [marimo](https://marimo.io/), or
[ttyd](https://github.com/tsl0922/ttyd) for a web terminal). This doc covers
the specific pattern for that setup: preferring a `pca`-issued certificate
over Caddy's own certificate options, opportunistically.

## Why these apps don't use Caddy's own automatic HTTPS

Caddy normally manages its own certificates automatically — either via a
public ACME CA (Let's Encrypt) for a real public hostname, or via its
built-in local/internal CA (`tls internal`) for anything else. On a
Janelia-style compute node, both of those are the wrong fit:

- There's no public hostname to get an ACME cert for (the app is bound to a
  compute node's ephemeral, internal address).
- Caddy's internal-CA issuer installs its root into the OS trust store the
  first time it's used, and that install step shells out to `sudo` — which
  hangs indefinitely on a host with no interactive `sudo` session (exactly
  the situation on a compute node reached only through a batch scheduler or
  Fileglancer job). See `container/https-wrap.sh` in
  [marimo_ai_sandbox](https://github.com/JaneliaSciComp/marimo_ai_sandbox)
  for the discovery of this failure mode.

So these apps set `auto_https off` and hand Caddy a **static cert file**
directly via the `tls <cert_file> <key_file>` directive instead, generating
that cert themselves with `openssl` — a self-signed cert with a 10-year
validity, regenerated only when the hostname changes (new compute-node
allocation).

## The self-signed-cert problem, restated for this context

A self-signed cert works, but it's exactly the case Fileglancer's own docs
warn about: *"Do not use self-signed certificates, as they don't work
properly with CORS and JavaScript fetch operations"*
(`fileglancer/docs/Development.md`). Concretely, for a Caddy-fronted app:

- Every first connection shows a full-page untrusted-certificate interstitial
  that a human has to click through — fine for a solo dev server, worse for
  a classroom of students all hitting a shared URL for the first time
  (`janelia-mojo-sandbox`'s exact use case).
- Anything that isn't a human clicking "proceed anyway" — a background
  `fetch()`/XHR from another origin, a health-check script, another
  service's HTTP client — fails outright instead of showing an interstitial,
  since there's no "click through" affordance outside a browser's top-level
  navigation.

`pca` exists to make the cert *not* self-signed from the client's
perspective: `pca init` installs one root CA into the local trust store(s)
a single time, and every `pca issue`d cert after that is signed by a CA the
client already trusts — so there's nothing to click through and no
CORS/`fetch` failure, without needing a real org-PKI/ACME certificate for an
address that doesn't have a stable public hostname anyway.

## The integration pattern

The change is entirely inside whatever function currently calls
`openssl req -x509 ...` to generate the self-signed cert — the Caddy
config itself (the `tls <cert_file> <key_file>` directive) doesn't change at
all, since a `pca`-issued cert is just another cert/key file pair on disk.
Make that function:

1. Check whether the `pca` CLI is on `PATH` (`command -v pca`).
2. If so, call `pca issue --name <stable-name> --san <hostname> [...]` — the
   same stable-name-per-service, issue-on-every-startup pattern described in
   [`Integration.md`](Integration.md) — and use the resulting
   `~/.local/share/personal-certificate-authority/certs/<name>/{cert.pem,key.pem}`
   as the cert/key files.
3. If `pca` isn't on `PATH`, or `pca issue` fails (e.g. `pca init` was never
   run, so there's no root CA yet), fall back to the existing self-signed
   generation unchanged.

That order matters: this must be **purely opportunistic**, never a hard
requirement. An app that only worked when `pca` happened to be installed
would break for everyone who hasn't opted in — the whole point is that nothing
changes for them.

```bash
# Drop-in replacement for a self-signed-cert generator function. Sets
# CERT_FILE/KEY_FILE either way; the caller (e.g. a Caddyfile's
# `tls ${CERT_FILE} ${KEY_FILE}` line) doesn't need to know which path ran.
generate_cert() {
    local cert_dir="$1" cert_name="$2"
    HOST_NAME="$(hostname -f 2>/dev/null || hostname)"

    if command -v pca >/dev/null 2>&1; then
        local pca_data_dir="${PCA_DATA_DIR:-$HOME/.local/share/personal-certificate-authority}"
        local pca_cert="$pca_data_dir/certs/$cert_name/cert.pem"
        local pca_key="$pca_data_dir/certs/$cert_name/key.pem"
        if pca issue --name "$cert_name" --san "$HOST_NAME" --san localhost --san 127.0.0.1 \
            && [[ -f "$pca_cert" && -f "$pca_key" ]]; then
            CERT_FILE="$pca_cert"
            KEY_FILE="$pca_key"
            echo ">> Using pca-issued HTTPS cert for ${HOST_NAME}"
            return 0
        fi
        echo ">> WARNING: pca is on PATH but issuing a certificate failed; falling back to a self-signed cert." >&2
    fi

    # ... existing self-signed `openssl req -x509 ...` generation, unchanged ...
}
```

A few details worth calling out:

- **No Caddy config change.** `tls ${CERT_FILE} ${KEY_FILE}` in the
  Caddyfile stays exactly as it was; only where those two files come from
  changes.
- **`pca issue` is idempotent** (see `Integration.md`), so calling it on
  every startup — even when the existing cert already covers the current
  hostname and isn't near expiry — is a fast no-op, not a repeated
  regeneration. This mirrors the existing self-signed path's own
  reuse-unless-hostname-changed check.
- **No live-reload concern.** Caddy loads a static `tls` cert file once at
  config load; it doesn't watch it for changes. That's fine here because
  each of these apps starts a fresh Caddy process per job/session anyway, so
  a cert change always coincides with a Caddy restart, never a
  currently-running Caddy needing to pick up a new file.
- **`PCA_DATA_DIR` override**: respect it if set, matching `pca`'s own
  convention, so a caller can point at a non-default `pca` data directory
  without needing a `pca`-specific flag added to the wrapper itself.

## Worked examples

This pattern was implemented (and tested against a stub `pca` binary
simulating success/failure/absence, then opened as real PRs) against two
existing Caddy-fronted, Fileglancer-launched apps that share one
`caddy-lib.sh` helper file:

- [JaneliaSciComp/marimo_ai_sandbox#22](https://github.com/JaneliaSciComp/marimo_ai_sandbox/pull/22) —
  fronts a [marimo](https://marimo.io/) notebook server and a
  [ttyd](https://github.com/tsl0922/ttyd) web terminal.
- [JaneliaSciComp/janelia-mojo-sandbox#1](https://github.com/JaneliaSciComp/janelia-mojo-sandbox/pull/1) —
  fronts a shared classroom `ttyd` terminal; ported verbatim from the
  `marimo_ai_sandbox` change, matching that repo's existing convention that
  `container/caddy-lib.sh` is kept byte-for-byte identical between the two.

Both diffs are small and confined to the one cert-generation function (plus
a README paragraph); neither touches the Caddyfile template, the reverse
proxy setup, or anything else in the surrounding app.
