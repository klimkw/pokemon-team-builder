from fastapi import HTTPException, Request
from app.settings import APP_ORIGIN


async def require_same_origin(request: Request):
    origin = request.headers.get("origin")
    if origin is not None and origin != APP_ORIGIN:
        raise HTTPException(403, "Origin not allowed")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site request not allowed")
