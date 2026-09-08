# CLAUDE.md - personal-certificate-authority Development Guide

## Critical Rule: Always Use Pixi

Never invoke `python`, `pytest`, `pip`, or `mkcert` directly — always through
pixi (`pixi run ...`), which manages the environment including the `mkcert`
binary itself (installed via conda-forge, not manually).

## Project Overview

A `pca` CLI (+ small FastAPI web app) that wraps `mkcert` to provide a
personal root CA and issued server TLS certificates for local apps such as
Fileglancer, plus a download/trust-instructions page for the common case
where this runs on a remote host and the user's browser is elsewhere.

- `personal_certificate_authority/mkcert_wrapper.py` — all `mkcert` subprocess calls; pins `CAROOT` to `data_dir/mkcert`
- `personal_certificate_authority/certinfo.py` — the only place `cryptography` is used, and only for reading certs, never generating them
- `personal_certificate_authority/cli.py` — `pca` click CLI
- `personal_certificate_authority/server.py`, `templates/` — `pca serve` web app

## Common tasks

```bash
pixi run pca init
pixi run pca issue --name NAME --san SAN
pixi run pca serve
pixi run -e test test
```

## Testing

Tests spin up a real `mkcert` under an isolated `tmp_path` CAROOT (see
`tests/conftest.py`'s `settings`/`initialized_settings` fixtures) rather than
mocking `mkcert` — the whole point of this project is correctly driving the
real binary, so tests skip (not fail) if `mkcert` isn't on `PATH`.
