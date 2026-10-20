"""Compatibility entry point; prefer python -m app.jobs.scanner."""
from app.jobs.scanner import main

if __name__ == "__main__":
    raise SystemExit(main())
