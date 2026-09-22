"""End-to-end smoke tests against the real data in data/. The index is built once per module."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from exposure.api import app

EXPOSURE_KEYS = {
    "asset_id", "address", "asset_type", "insured_value_dkk", "station",
    "wet_days", "worst_3day_mm", "worst_3day_start", "worst_3day_end", "period",
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as client:  # the with-block runs the lifespan that builds the index
        yield client


def test_single_asset_exposure(client):
    response = client.get("/assets/A-200975/exposure")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == EXPOSURE_KEYS
    assert (body["asset_id"], body["address"], body["asset_type"], body["insured_value_dkk"]) == (
        "A-200975", "Lindevej 1", "industrial", 14707000
    )

    assert set(body["station"]) == {"station_id", "station_name", "distance_m"}
    assert body["station"]["distance_m"] > 0
    # Recomputed independently with pyproj on the current station rows: DK1469 at 10470.5 m,
    # the runner-up (DK1329) is 26 km away, so this is not a near tie.
    assert body["station"]["station_id"] == "DK1469"
    assert body["station"]["distance_m"] == pytest.approx(10470.5, abs=5.0)

    assert isinstance(body["wet_days"], int) and body["wet_days"] >= 0
    assert body["worst_3day_mm"] >= 0
    start, end = date.fromisoformat(body["worst_3day_start"]), date.fromisoformat(body["worst_3day_end"])
    assert (end - start).days == 2

    assert set(body["period"]) == {"start", "end", "days_observed"}
    assert (body["period"]["start"], body["period"]["end"]) == ("2025-01-01", "2026-06-30")
    assert 0 < body["period"]["days_observed"] <= 546  # 2025-01-01..2026-06-30 inclusive

    # Values from an independent pandas recomputation (drop precip<0, drop conflicting duplicates,
    # local days in Europe/Copenhagen, rolling 3-date window with missing days as 0) for DK1469.
    assert body["wet_days"] == 26
    assert body["worst_3day_mm"] == pytest.approx(72.5, abs=0.05)
    assert (body["worst_3day_start"], body["worst_3day_end"]) == ("2026-01-13", "2026-01-15")


def test_ambiguous_asset_is_409(client):
    assert client.get("/assets/A-200342/exposure").status_code == 409


def test_unknown_asset_is_404(client):
    assert client.get("/assets/NOPE/exposure").status_code == 404


def test_portfolio_by_type_is_ranked(client):
    response = client.get("/portfolio/exposure", params={"asset_type": "public"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"count", "ranking", "assets", "skipped"}
    assets = body["assets"]
    assert body["count"] == len(assets) > 0
    assert all(a["asset_type"] == "public" for a in assets)
    assert [a["rank"] for a in assets] == list(range(1, len(assets) + 1))
    sort_key = [(-a["worst_3day_mm"], -a["wet_days"], a["asset_id"]) for a in assets]
    assert sort_key == sorted(sort_key)  # worst 3-day desc, wet days desc, id asc
    assert body["skipped"] == {"unknown": [], "ambiguous": []}


def test_portfolio_by_ids_reports_skipped(client):
    response = client.get("/portfolio/exposure", params={"ids": "A-200975,A-206420,A-200342,NOPE"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert {a["asset_id"] for a in body["assets"]} == {"A-200975", "A-206420"}
    assert body["skipped"]["ambiguous"] == ["A-200342"]
    assert body["skipped"]["unknown"] == ["NOPE"]


def test_portfolio_requires_exactly_one_filter(client):
    assert client.get("/portfolio/exposure").status_code == 400
    both = client.get("/portfolio/exposure", params={"asset_type": "public", "ids": "A-200975"})
    assert both.status_code == 400


def test_portfolio_unknown_type_is_400(client):
    assert client.get("/portfolio/exposure", params={"asset_type": "castle"}).status_code == 400


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
