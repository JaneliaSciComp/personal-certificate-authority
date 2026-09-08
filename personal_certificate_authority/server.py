from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from personal_certificate_authority import certinfo, store
from personal_certificate_authority.settings import get_settings

TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app() -> FastAPI:
    app = FastAPI(title="Personal Certificate Authority")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        settings = get_settings()
        cert_file, _ = store.root_ca_paths(settings)
        if not cert_file.exists():
            return templates.TemplateResponse(
                request, "not_initialized.html", {}, status_code=404
            )
        info = certinfo.read_cert(cert_file)
        return templates.TemplateResponse(
            request,
            "trust.html",
            {
                "common_name": info.common_name,
                "fingerprint": info.sha256_fingerprint,
                "not_valid_after": info.not_valid_after.isoformat(),
            },
        )

    @app.get("/download/rootCA.pem")
    def download_root_ca():
        settings = get_settings()
        cert_file, _ = store.root_ca_paths(settings)
        if not cert_file.exists():
            raise HTTPException(status_code=404, detail="No root CA found. Run `pca init` first.")
        return FileResponse(
            cert_file,
            media_type="application/x-x509-ca-cert",
            filename="rootCA.pem",
        )

    return app


app = create_app()
