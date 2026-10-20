from fastapi import HTTPException, Request
from app.settings import APP_ORIGIN


async def require_same_origin(request: Request):
    origin = request.headers.get("origin")
    # Admin requests may also originate from the API's own Swagger docs.
    # Compare with the validated Host header instead of accepting arbitrary origins.
    docs_origin = str(request.base_url).rstrip('/')
    allowed = {APP_ORIGIN}
    if request.url.path.startswith('/api/admin/'):
        allowed.add(docs_origin)
    if origin is not None and origin not in allowed:
        raise HTTPException(403, "Origin not allowed")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site request not allowed")
