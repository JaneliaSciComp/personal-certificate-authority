from fastapi.testclient import TestClient

import personal_certificate_authority.settings as settings_module
from personal_certificate_authority.server import create_app
from personal_certificate_authority.settings import Settings


def _client_with(settings: Settings) -> TestClient:
    settings_module._settings = settings
    return TestClient(create_app())


def test_index_404_when_not_initialized(settings: Settings):
    client = _client_with(settings)
    response = client.get("/")
    assert response.status_code == 404
    assert "pca init" in response.text


def test_index_shows_ca_info_when_initialized(initialized_settings: Settings):
    client = _client_with(initialized_settings)
    response = client.get("/")
    assert response.status_code == 200
    assert "Download CA Certificate" in response.text


def test_download_root_ca(initialized_settings: Settings):
    client = _client_with(initialized_settings)
    response = client.get("/download/rootCA.pem")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-x509-ca-cert"
    assert b"BEGIN CERTIFICATE" in response.content


def test_download_root_ca_404_when_missing(settings: Settings):
    client = _client_with(settings)
    response = client.get("/download/rootCA.pem")
    assert response.status_code == 404
