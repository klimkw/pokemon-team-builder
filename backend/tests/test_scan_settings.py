import pytest
from app.settings import positive_setting


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "", "abc", " 24", "true"])
def test_scan_settings_reject_invalid_values(monkeypatch, value):
    for name in ["CATALOG_SCAN_INTERVAL_HOURS", "CHANGE_ALERT_WINDOW_DAYS"]:
        monkeypatch.setenv(name, value)
        with pytest.raises(ValueError, match=name):
            positive_setting(name, 7)


def test_scan_settings_defaults_and_overrides(monkeypatch):
    monkeypatch.delenv("CATALOG_SCAN_INTERVAL_HOURS", raising=False)
    assert positive_setting("CATALOG_SCAN_INTERVAL_HOURS", 24) == 24
    monkeypatch.setenv("CATALOG_SCAN_INTERVAL_HOURS", "6")
    monkeypatch.setenv("CHANGE_ALERT_WINDOW_DAYS", "14")
    assert positive_setting("CATALOG_SCAN_INTERVAL_HOURS", 24) == 6
    assert positive_setting("CHANGE_ALERT_WINDOW_DAYS", 7) == 14
