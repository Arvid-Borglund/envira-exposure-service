"""Cleaning rules on hand-built rows, plus one check that the real files load as expected."""

from pathlib import Path

import pandas as pd

from exposure.data import clean_assets, clean_observations, clean_stations, load_dataset

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
NAN = float("nan")  # what read_csv yields for an empty field


def raw_observations(rows):
    return pd.DataFrame(rows, columns=["station_id", "observed_at", "precip_mm", "temp_c"])


def raw_stations(rows):
    return pd.DataFrame(rows, columns=["station_id", "station_name", "lat", "lon", "valid_from", "valid_to"])


def raw_assets(rows):
    return pd.DataFrame(rows, columns=["asset_id", "address", "x", "y", "asset_type", "insured_value_dkk"])


def test_negative_sentinels_are_dropped_and_counted():
    raw = raw_observations(
        [
            ("S", "2025-01-01T05:00:00Z", 1.0, 5.0),
            ("S", "2025-01-01T11:00:00Z", -999.0, 5.0),
            ("S", "2025-01-01T17:00:00Z", -9999.0, 5.0),
            ("S", "2025-01-01T23:00:00Z", 0.0, 5.0),
        ]
    )
    obs, counts = clean_observations(raw)
    assert sorted(obs["precip_mm"]) == [0.0, 1.0]
    assert 2 in counts.values()


def test_conflicting_duplicate_pair_drops_both_rows():
    raw = raw_observations(
        [
            ("S", "2025-01-01T05:00:00Z", 1.0, 5.0),
            ("S", "2025-01-01T05:00:00Z", 2.0, 5.0),
            ("S", "2025-01-01T11:00:00Z", 3.0, 5.0),
        ]
    )
    obs, _ = clean_observations(raw)
    assert list(obs["precip_mm"]) == [3.0]


def test_identical_duplicate_pair_keeps_one_row():
    raw = raw_observations(
        [
            ("S", "2025-01-01T05:00:00Z", 1.0, 5.0),
            ("S", "2025-01-01T05:00:00Z", 1.0, 5.0),
        ]
    )
    obs, _ = clean_observations(raw)
    assert list(obs["precip_mm"]) == [1.0]
    assert not obs.duplicated(["station_id", "observed_at"]).any()


def test_observed_at_is_parsed_to_utc_datetime():
    obs, _ = clean_observations(raw_observations([("S", "2025-03-01T23:00:00Z", 1.0, 5.0)]))
    assert list(obs.columns) == ["station_id", "observed_at", "precip_mm"]
    assert isinstance(obs["observed_at"].dtype, pd.DatetimeTZDtype)
    assert str(obs["observed_at"].dt.tz) == "UTC"
    assert obs["observed_at"].iloc[0] == pd.Timestamp("2025-03-01T23:00:00Z")


def test_clean_assets_drops_every_row_of_a_duplicated_id():
    raw = raw_assets(
        [
            ("A-1", "Gade 1", 500000.0, 6100000.0, "residential", 1000),
            ("A-2", "Gade 2", 500100.0, 6100100.0, "public", 2000),
            ("A-1", "Gade 9", 900000.0, 6400000.0, "commercial", 9000),
        ]
    )
    assets, ambiguous, counts = clean_assets(raw)
    assert ambiguous == frozenset({"A-1"})
    assert list(assets.columns) == list(raw.columns)
    assert assets.to_dict("records") == [
        {"asset_id": "A-2", "address": "Gade 2", "x": 500100.0, "y": 6100100.0, "asset_type": "public", "insured_value_dkk": 2000}
    ]
    assert all(isinstance(v, int) for v in counts.values())
    assert any(v > 0 for v in counts.values())  # the drop is counted, whichever key is used


def test_clean_stations_keeps_current_row_of_relocated_station():
    raw = raw_stations(
        [
            ("DK1", "Station DK1", 55.0, 12.0, "2025-01-01", "2025-06-30"),
            ("DK2", "Station DK2", 56.0, 10.0, "2025-01-01", NAN),
            ("DK1", "Station DK1", 55.5, 12.5, "2025-07-01", NAN),
        ]
    )
    stations, _ = clean_stations(raw)
    assert list(stations.columns) == ["station_id", "station_name", "lat", "lon"]
    by_id = stations.set_index("station_id")
    assert sorted(by_id.index) == ["DK1", "DK2"]
    assert (by_id.loc["DK1", "lat"], by_id.loc["DK1", "lon"]) == (55.5, 12.5)
    assert (by_id.loc["DK2", "lat"], by_id.loc["DK2", "lon"]) == (56.0, 10.0)


def test_load_dataset_on_real_files():
    ds = load_dataset(DATA_DIR)
    assert len(ds.assets) == 4960  # 5040 rows, 40 ids appear twice and are dropped entirely
    assert ds.assets["asset_id"].is_unique
    assert len(ds.ambiguous_asset_ids) == 40
    assert {"A-200342", "A-200561", "A-200720"} <= ds.ambiguous_asset_ids
    assert len(ds.stations) == 120
    assert ds.stations["station_id"].is_unique
    assert (ds.observations["precip_mm"] >= 0).all()
    assert not ds.observations.duplicated(["station_id", "observed_at"]).any()
    assert ds.cleaning and all(isinstance(v, int) for v in ds.cleaning.values())
