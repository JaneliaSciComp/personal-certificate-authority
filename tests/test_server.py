import shutil

import pytest
from fastapi.testclient import TestClient

import personal_certificate_authority.settings as settings_module
from personal_certificate_authority.server import create_app
from personal_certificate_authority.settings import Settings


def _client_with(settings: Settings) -> TestClient:
    settings_module._settings = settings
    return TestClient(create_app())


def test_index_auto_initializes_when_not_initialized(settings: Settings):
    if shutil.which("mkcert") is None:
        pytest.skip("mkcert binary not available on PATH")
    client = _client_with(settings)

    response = client.get("/")
    assert response.status_code == 200
    assert "didn't exist yet" in response.text

    # A second visit shouldn't re-show the just-initialized banner.
    response = client.get("/")
    assert response.status_code == 200
    assert "didn't exist yet" not in response.text


def test_index_shows_ca_info_when_initialized(initialized_settings: Settings):
    client = _client_with(initialized_settings)
    response = client.get("/")
    assert response.status_code == 200
    assert "Download CA Certificate" in response.text
    assert "didn't exist yet" not in response.text


def test_index_500_when_mkcert_missing(settings: Settings):
    settings.mkcert_binary = "definitely-not-a-real-binary"
    client = _client_with(settings)
    response = client.get("/")
    assert response.status_code == 500
    assert "mkcert" in response.text


def test_index_warns_when_pca_not_on_path(initialized_settings: Settings, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None if name == "pca" else "/usr/bin/" + name)
    client = _client_with(initialized_settings)
    response = client.get("/")
    assert response.status_code == 200
    assert "pixi global install" in response.text


def test_index_no_warning_when_pca_on_path(initialized_settings: Settings, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
    client = _client_with(initialized_settings)
    response = client.get("/")
    assert response.status_code == 200
    assert "pixi global install" not in response.text


def test_download_root_ca(initialized_settings: Settings):
    client = _client_with(initialized_settings)
    response = client.get("/download/rootCA.pem")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-x509-ca-cert"
    assert b"BEGIN CERTIFICATE" in response.content


def test_download_root_ca_auto_initializes(settings: Settings):
    if shutil.which("mkcert") is None:
        pytest.skip("mkcert binary not available on PATH")
    client = _client_with(settings)
    response = client.get("/download/rootCA.pem")
    assert response.status_code == 200
    assert b"BEGIN CERTIFICATE" in response.content


def test_download_root_ca_500_when_mkcert_missing(settings: Settings):
    settings.mkcert_binary = "definitely-not-a-real-binary"
    client = _client_with(settings)
    response = client.get("/download/rootCA.pem")
    assert response.status_code == 500
