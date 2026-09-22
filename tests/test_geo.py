"""CRS reconciliation and nearest-station lookup on hand-placed points."""

import math

import pandas as pd
from pyproj import Transformer

from exposure.geo import ASSET_CRS, STATION_CRS, nearest_station, stations_to_asset_crs


def test_crs_constants_match_the_data():
    assert ASSET_CRS == "EPSG:25832"  # assets.csv x/y are ETRS89 / UTM 32N metres
    assert STATION_CRS == "EPSG:4326"  # stations.csv lat/lon


def test_copenhagen_station_lands_in_utm_zone_32n():
    stations = pd.DataFrame(
        [{"station_id": "DK1", "station_name": "Station DK1", "lat": 55.676, "lon": 12.568}]
    )
    out = stations_to_asset_crs(stations)

    assert "x" not in stations.columns  # input is not mutated
    assert {"station_id", "station_name", "lat", "lon", "x", "y"} <= set(out.columns)
    x, y = float(out["x"].iloc[0]), float(out["y"].iloc[0])
    assert abs(x - 724_000) < 2_000 and abs(y - 6_175_000) < 2_000
    assert 400_000 < x < 900_000 and 6_000_000 < y < 6_500_000

    # Same answer as pyproj with lon/lat in that order: guards against swapped axes.
    ex, ey = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True).transform(12.568, 55.676)
    assert abs(x - ex) < 1.0 and abs(y - ey) < 1.0


def stations_xy(rows):
    return pd.DataFrame(rows, columns=["station_id", "x", "y"])


def test_nearest_station_picks_the_closest_with_euclidean_distance():
    assets = pd.DataFrame([{"asset_id": "A-1", "x": 1000.0, "y": 1000.0}])
    stations = stations_xy([("S-far", 5000.0, 5000.0), ("S-near", 1300.0, 1400.0), ("S-mid", 2000.0, 1000.0)])
    out = nearest_station(assets, stations)

    assert list(out.columns) == ["asset_id", "station_id", "distance_m"]
    assert out.to_dict("records") == [{"asset_id": "A-1", "station_id": "S-near", "distance_m": 500.0}]
    assert out["distance_m"].iloc[0] == math.hypot(300.0, 400.0)


def test_nearest_station_ties_go_to_smallest_station_id():
    assets = pd.DataFrame([{"asset_id": "A-1", "x": 0.0, "y": 0.0}, {"asset_id": "A-2", "x": 100.0, "y": 0.0}])
    stations = stations_xy([("S-2", 100.0, 0.0), ("S-1", 0.0, 100.0)])  # S-2 listed first on purpose
    out = nearest_station(assets, stations).set_index("asset_id")

    assert len(out) == 2
    assert out.loc["A-1", "station_id"] == "S-1"  # both at 100 m; smallest id wins, not first row
    assert out.loc["A-1", "distance_m"] == 100.0
    assert out.loc["A-2", "station_id"] == "S-2"
    assert out.loc["A-2", "distance_m"] == 0.0
