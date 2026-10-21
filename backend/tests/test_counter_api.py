import pytest


def test_preview_uses_current_ordered_lineup_and_does_not_write_teams(signed_in):
    payload = {"name": "Original", "pokemon_ids": [1, 7]}
    saved = signed_in.post("/api/teams", json=payload).json()
    before = signed_in.get("/api/teams").json()
    response = signed_in.post("/api/teams/counter-preview", json={"pokemon_ids": [25, 1]})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["size"] == 2
    assert [match["opponent"]["id"] for match in result["matchups"]] == [25, 1]
    assert [match["opponent_position"] for match in result["matchups"]] == [0, 1]
    generated = [match["counter"]["id"] for match in result["matchups"]]
    assert len(set(generated)) == 2
    assert result["safe_count"] == sum(match["safe"] for match in result["matchups"])
    assert result["model_version"] == "safe-coverage-v1"
    for match in result["matchups"]:
        duel = match["simulation"]
        assert duel["model_version"] == "paired-base-stats-v1"
        assert 1 <= len(duel["turns"]) <= 200
        assert duel["outgoing"]["effectiveness"] == match["outgoing_multiplier"]
        assert duel["incoming"]["effectiveness"] == match["incoming_multiplier"]
    assert result["chart_version"].startswith("sha256:")
    assert signed_in.get("/api/teams").json() == before
    assert signed_in.get(f"/api/teams/{saved['id']}").json() == saved
    assert signed_in.post("/api/teams/counter-preview", json={"pokemon_ids": [25, 1]}).json() == result
    created = signed_in.post("/api/teams", json={"name": "Counter", "pokemon_ids": generated})
    assert created.status_code == 201
    assert len(signed_in.get("/api/teams").json()) == 2


def test_preview_requires_authentication_and_same_origin(client, signed_in):
    payload = {"pokemon_ids": [1]}
    assert signed_in.post("/api/teams/counter-preview", json=payload, headers={"Origin": "https://other.example"}).status_code == 403
    signed_in.post("/api/auth/logout")
    assert client.post("/api/teams/counter-preview", json=payload).status_code == 401


def test_preview_validation_and_insufficient_catalog_preserve_teams(signed_in):
    for payload in [{"pokemon_ids": []}, {"pokemon_ids": [1] * 7}, {"pokemon_ids": [True]},
                    {"pokemon_ids": [1.5]}, {"pokemon_ids": ["1"]}, {"pokemon_ids": [0]},
                    {"pokemon_ids": [1], "user_id": "someone-else"}, {}]:
        assert signed_in.post("/api/teams/counter-preview", json=payload).status_code == 422
    unknown = signed_in.post("/api/teams/counter-preview", json={"pokemon_ids": [999999]})
    assert unknown.status_code == 422
    assert unknown.json()["detail"]["code"] == "UNKNOWN_POKEMON"
    small = signed_in.post("/api/teams/counter-preview", json={"pokemon_ids": [1] * 4})
    assert small.status_code == 409
    assert small.json()["detail"]["code"] == "INSUFFICIENT_CATALOG"
    assert signed_in.get("/api/teams").json() == []
