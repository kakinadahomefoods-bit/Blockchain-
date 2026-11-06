import pytest
from app import db

@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ADMIN_PASSWORD', 'correct-strong-password')
    monkeypatch.setenv('HMAC_KEY', 'c1' * 32)
    monkeypatch.setenv('CHAIN_BACKEND', 'local')
    db.initialize()
    yield
