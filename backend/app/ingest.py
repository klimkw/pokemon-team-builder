"""Compatibility entry point; prefer python -m app.jobs.ingest."""
from app.jobs.ingest import main

if __name__ == "__main__":
    raise SystemExit(main())
