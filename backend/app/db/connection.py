"""Adapt hosted PostgreSQL URLs without weakening TLS verification."""
import ssl
from sqlalchemy.engine import make_url


def connection_options(value):
    url = make_url(value)
    options = {}
    if url.drivername in ("postgres", "postgresql", "postgresql+asyncpg"):
        url = url.set(drivername="postgresql+asyncpg")
        query = dict(url.query)
        mode = query.pop("sslmode", None)
        binding = query.pop("channel_binding", None)
        if binding not in (None, "prefer", "require", "disable"):
            raise ValueError("Unsupported channel_binding value")
        if mode in ("require", "verify-ca", "verify-full"):
            # asyncpg doesn't accept libpq's channel_binding parameter. Require
            # trusted certificates and hostname validation instead of plain TLS.
            options["ssl"] = ssl.create_default_context()
        elif mode is not None:
            raise ValueError("Hosted sslmode must be require, verify-ca, or verify-full")
        url = url.set(query=query)
    return url, options
