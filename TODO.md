# TODO

## Consider a hybrid mkcert/cryptography design if mkcert bit-rots

**Status:** deferred — not worth doing until there's a concrete reason to.

**Context:** `mkcert` (the engine `mkcert_wrapper.py` wraps for all CA/cert
generation) has had no real code changes since April 2022 (last release
v1.4.4; the only commit since is an August 2024 README fix). It isn't
archived and nothing is currently broken, but it's effectively unmaintained.

**Why not act now:** the part of mkcert doing work that's genuinely hard to
reimplement is OS/browser trust-store installation (`-install`/`-uninstall`
against NSS/Keychain/Windows cert stores) — the part most exposed to future
OS/browser changes. Cert *generation* is a thin wrapper over `crypto/x509`
and is unlikely to bit-rot on its own. Nothing has actually broken, so
there's no evidence yet that this dormancy is a real problem.

**If a real issue does show up** (e.g. a macOS/Windows/Firefox update breaks
`-install`, or a security issue surfaces in mkcert with no fix forthcoming),
consider this hybrid instead of dropping mkcert entirely:

- Generate the root CA and leaf certs ourselves with the `cryptography`
  library (already a dependency, currently only used read-only in
  `certinfo.py`) — full control, and removes exposure to mkcert for the part
  of the workflow exercised on every `pca issue`.
- Keep calling `mkcert -install`/`-uninstall` (pointed at our own CAROOT,
  containing our own self-generated `rootCA.pem`) for *only* the trust-store
  step, since that's the piece worth not reinventing.
- `mkcert_wrapper.py` would shrink to just the trust-store calls; a new
  `ca.py`/`leaf.py` would take over generation (mirroring the design
  considered — and set aside in favor of full mkcert — during initial
  planning).

Considered and rejected as the general fix: switching to Caddy. Caddy is
actively maintained and its local-CA code (via `smallstep/certificates`/
`smallstep/truststore`) is real infrastructure, but its model is either
"Caddy terminates TLS for you" (collapses to an nginx-proxy-style
architecture, losing the end-to-end-to-the-backend property this project is
for) or "run a persistent `acme_server` and give every consumer its own ACME
client" (real moving parts vs. mkcert's one-shot synchronous file output).
Neither fits this project's no-daemon, one-shot-CLI shape.

## Make `pca` installable via `pixi global install`/conda-forge

**Status:** deferred — a manual wrapper-script workaround exists and is
documented (`docs/Integration.md`, "Getting `pca` itself onto PATH").

**Context:** this project isn't published anywhere, and `pixi global
install --path`/`--git` fails against it as-is ("the pyproject.toml does not
describe a package") because it's a plain hatchling/pip package, not built
with pixi's newer package/build system (`[tool.pixi.package]` + a
pixi-build backend). `pip install`/`pipx install` do work, but need
Python ≥3.12 as the installing interpreter, which isn't every host's system
default.

This matters beyond convenience: every "if `pca` is on PATH, use it"
integration (see `docs/CaddyIntegration.md`, and the
`marimo_ai_sandbox`/`janelia-mojo-sandbox` PRs) silently no-ops until
`pca` is actually reachable on `PATH`, and today that requires each host to
set up the wrapper-script shim by hand.

**If this friction turns out to matter in practice** (multiple hosts/users
needing the shim), consider either adding pixi-build packaging to this repo
so `pixi global install --git .../personal-certificate-authority` works
natively, or publishing to conda-forge properly (heavier, but would also let
`fileglancer`'s own `pyproject.toml` declare `pca` as a normal dependency
instead of every consumer reinventing the `command -v pca` check).
