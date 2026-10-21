"""Shared definition of a live refresh that includes the type chart."""
from typing import Any, Literal, TypedDict
from sqlalchemy import or_
from app.db.models import ScanRun

ScanStatus = Literal["running", "succeeded", "partial", "failed", "interrupted", "skipped"]


class ScanSummary(TypedDict, total=False):
    scope: Literal["full", "sample"]
    source: str
    types: dict[str, int]
    pokemon: dict[str, Any]
    errors: dict[str, str]
    error: str
    reason: str
    demo_id: str


def is_live_refresh(summary: ScanSummary) -> bool:
    return (summary.get("scope") == "full" and summary.get("types") is not None
            and summary.get("source") in (None, "upstream"))


def live_refresh_conditions():
    return (
        ScanRun.summary["scope"].as_string() == "full",
        ScanRun.summary["types"].as_string().is_not(None),
        or_(ScanRun.summary["source"].as_string().is_(None),
            ScanRun.summary["source"].as_string() == "upstream"),
    )
