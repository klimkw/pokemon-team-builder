from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app.frontend import mount_frontend


def test_bundle_and_api_share_origin_without_masking_missing_routes(tmp_path):
    (tmp_path / 'index.html').write_text('<html>Team builder</html>')
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets' / 'app.js').write_text('console.log("loaded")')
    app = FastAPI()

    @app.get('/api/health')
    def health():
        return {'status': 'ok'}

    mount_frontend(app, str(tmp_path))
    with TestClient(app) as client:
        assert 'Team builder' in client.get('/').text
        assert 'Team builder' in client.get('/counter-method').text
        assert 'Team builder' in client.get('/architecture').text
        assert client.get('/unknown-page').status_code == 404
        assert client.get('/assets/app.js').status_code == 200
        assert client.get('/api/health').json() == {'status': 'ok'}
        assert client.get('/api/missing').status_code == 404
        assert client.get('/assets/missing.js').status_code == 404
        assert client.get('/.env').status_code == 404


def test_missing_bundle_fails_startup(tmp_path):
    with pytest.raises(RuntimeError, match='FRONTEND_DIST'):
        mount_frontend(FastAPI(), str(tmp_path))
