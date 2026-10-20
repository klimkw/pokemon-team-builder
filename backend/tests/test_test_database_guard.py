import pytest
from conftest import validated_postgres_url


def test_postgres_tests_refuse_missing_or_development_database_urls(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://dev:dev@localhost/pokemon")
    for value in [None, "sqlite+aiosqlite:///pokemon_test", "postgresql+asyncpg://dev:dev@localhost/pokemon",
                  "postgresql+asyncpg://dev:dev@localhost/postgres"]:
        with pytest.raises(pytest.UsageError):
            validated_postgres_url(value)
    intended = "postgresql+asyncpg://test:test@localhost/pokemon_test"
    assert validated_postgres_url(intended) == intended
