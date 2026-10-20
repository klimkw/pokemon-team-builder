# Python workflow with uv

The backend uses uv to resolve Python dependencies, create its environment, and install
the locked versions. Docker still supplies Linux and Python 3.12; uv supplies the
project's packages. PostgreSQL, Alembic schema upgrades, and the Node frontend keep
their separate responsibilities.

## Project files

`backend/pyproject.toml` declares project metadata, Python >=3.12,<3.13, runtime
dependencies, and the dev dependency group. FastAPI Users stays pinned at 14.0.2;
the other declared ranges retain the previous requirements. The application runs from
source with package=false, so no distribution build or editable package installation
is required.

`backend/uv.lock` records exact direct and transitive versions, environment markers,
package sources, and artifact hashes. It is committed. `backend/.python-version`
selects Python 3.12 for uv commands. The generated .venv directory is ignored.
The old requirements files have been replaced so there is one dependency source.

During migration, the previously tested image's installed versions were captured and
used as temporary resolution constraints. Those constraints were removed after lock
creation, followed by another normal resolution and lock check. Both the final lock and actual uv-installed test environment preserved all 43
previously installed versions.
Extra packages for other platforms can appear in the universal lock without being
installed in the Linux image.

## Docker installation

Both backend Dockerfiles copy uv 0.13.3 from the official Astral image, pinned by version
and image digest. They copy pyproject.toml, uv.lock and .python-version before application
code, allowing the dependency layer to be reused when only source changes.

The API/scanner image runs `uv sync --locked --no-dev`. The test image runs
`uv sync --locked`, including the default dev group with pytest and aiosqlite.
`--locked` fails on metadata/lock disagreement instead of silently changing the lock.
Both create a Linux environment inside the image at /app/.venv. PATH points to its
executables, so the existing Alembic, Uvicorn, scanner and pytest commands use the uv
managed environment without resolving dependencies on each container start.

UV_PYTHON_DOWNLOADS=never tells uv to use the Python interpreter already supplied by
the Docker base image. UV_LINK_MODE=copy avoids requiring hard links across cache and
application filesystems. The backend Docker ignore file excludes host environments,
caches, and .env. Windows environments are not reused as Linux installations.

## Local commands

From backend with uv installed:

```bash
uv sync --locked
uv run --locked python -m pytest -q
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The module-based pytest invocation puts the source directory on Python's import
path. Since this project has package=false, a bare pytest executable does not install
or discover app as a package automatically.

The API and migration commands also require DATABASE_URL and APP_ORIGIN to be set for
the chosen host setup. Running uv does not automatically load the repository .env;
Compose loads it for containers. For local execution, export the required settings
or deliberately use uv's --env-file option with the appropriate file. The default
Compose database is not published to the host, so Docker remains the ready-to-run path.

To add a runtime dependency, use `uv add <package>`; use `uv add --dev <package>` for
a test tool. Both update metadata and the lock. Upgrade deliberately with
`uv lock --upgrade-package <package>` or `uv lock --upgrade`, then test and commit the
metadata/lock changes. Avoid manually editing resolved package entries in uv.lock.

For a runtime-only local environment, use `uv sync --locked --no-dev`. For a Python
version outside 3.12, update and test the project's version policy explicitly rather
than relying on whichever interpreter happens to be installed.

## Verification

The migration is verified through the real Docker install path, lock consistency,
comparison with the original installed-version baseline, PostgreSQL and SQLite tests,
and browser regression tests. Runtime/test environment inspection confirms test-only
packages are absent from the runtime image and present in the test image.
The uv environments passed 93 PostgreSQL tests, 84 SQLite tests with nine skips, and
all three Chromium E2E tests. All 43 installed baseline versions matched. Runtime
inspection confirmed /app/.venv/bin/python and absence of pytest/aiosqlite. The offline
lock check passed. Results are also recorded in TESTING.md and HANDOFF.md.

Official references: [uv projects](https://docs.astral.sh/uv/guides/projects/) and
[uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/).
