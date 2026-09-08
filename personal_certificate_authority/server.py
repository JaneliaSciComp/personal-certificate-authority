import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from starlette.requests import Request

from personal_certificate_authority import certinfo, mkcert_wrapper, store
from personal_certificate_authority.settings import Settings, get_settings

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _ensure_root_ca(settings: Settings) -> tuple[Path, bool]:
    """Return (rootCA.pem path, just_initialized). Runs `pca init`'s
    equivalent on first visit so a fresh install doesn't dead-end on a
    "run pca init" message -- the whole point of this page is to be usable
    without a terminal. Lets MkcertNotFoundError propagate; that's the one
    case a web visit can't fix for itself."""
    cert_file, _ = store.root_ca_paths(settings)
    if cert_file.exists():
        return cert_file, False
    logger.info("No root CA found; initializing one for the web UI's first visit.")
    mkcert_wrapper.init(settings)
    return cert_file, True


def create_app() -> FastAPI:
    app = FastAPI(title="Personal Certificate Authority")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        settings = get_settings()
        try:
            cert_file, just_initialized = _ensure_root_ca(settings)
        except mkcert_wrapper.MkcertNotFoundError as exc:
            return templates.TemplateResponse(
                request, "mkcert_missing.html", {"error": str(exc)}, status_code=500
            )
        info = certinfo.read_cert(cert_file)
        return templates.TemplateResponse(
            request,
            "trust.html",
            {
                "common_name": info.common_name,
                "fingerprint": info.sha256_fingerprint,
                "not_valid_after": info.not_valid_after.isoformat(),
                "just_initialized": just_initialized,
                "pca_on_path": shutil.which("pca") is not None,
            },
        )

    @app.get("/download/rootCA.pem")
    def download_root_ca():
        settings = get_settings()
        try:
            cert_file, _ = _ensure_root_ca(settings)
        except mkcert_wrapper.MkcertNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return FileResponse(
            cert_file,
            media_type="application/x-x509-ca-cert",
            filename="rootCA.pem",
        )

    return app


app = create_app()
