"""Hosted URLs must work for both API and migrations without exposing secrets."""
import ssl
import pytest
from app.db.connection import connection_options


def test_neon_url_uses_asyncpg_and_verified_tls():
    url, options = connection_options('postgresql://user:p%40ss@ep-example.neon.tech/db?sslmode=require&channel_binding=require')
    assert url.drivername == 'postgresql+asyncpg'
    assert url.password == 'p@ss'
    assert not url.query
    assert options['ssl'].verify_mode == ssl.CERT_REQUIRED
    assert options['ssl'].check_hostname


def test_local_database_keeps_default_connection_behavior():
    url, options = connection_options('postgresql+asyncpg://pokemon:password@db/pokemon')
    assert url.host == 'db'
    assert options == {}


def test_sqlite_is_unchanged():
    url, options = connection_options('sqlite+aiosqlite:///test.db')
    assert url.drivername == 'sqlite+aiosqlite'
    assert options == {}


def test_insecure_hosted_sslmode_is_rejected():
    with pytest.raises(ValueError, match='sslmode'):
        connection_options('postgresql://user:password@host/db?sslmode=disable')
