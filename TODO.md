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

## ~~Make `pca` installable via `pixi global install`/conda-forge~~ — done

Implemented: `[tool.pixi.package]` + `pixi-build-python` (preview feature)
in `pyproject.toml` makes `pixi global install --path`/`--git` work
natively, pulling in `mkcert` and all Python deps and exposing `pca` on
`~/.pixi/bin`. Verified live against this repo. See `docs/Integration.md`,
"Getting `pca` itself onto PATH." The manual wrapper-script shim is kept
documented as a fallback for anyone who'd rather not touch their global
pixi environment.

Not done yet, and lower priority now that the above works: actually
publishing to conda-forge (would let `fileglancer`'s own `pyproject.toml`
declare `pca` as a normal dependency instead of every consumer doing its own
`command -v pca` check) — a real registry buys discoverability/versioning
that `pixi global install --git` alone doesn't, but isn't blocking anything
today.
