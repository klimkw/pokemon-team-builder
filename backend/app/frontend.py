"""Serve the demo bundle after API routes; unknown URLs remain 404s."""
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


def mount_frontend(app, directory):
    if not (Path(directory) / "index.html").is_file():
        raise RuntimeError("FRONTEND_DIST must contain the built frontend index.html")
    # This is a real client-side page, so direct visits need the React entrypoint.
    async def documentation_page():
        return FileResponse(Path(directory) / "index.html", headers={"Cache-Control": "no-cache"})

    for path in ("/counter-method", "/architecture"):
        app.add_api_route(path, documentation_page, methods=["GET"], include_in_schema=False)
    app.mount("/", StaticFiles(directory=directory, html=True), name="frontend")
