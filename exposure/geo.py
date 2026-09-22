"""Coordinate reference systems and nearest-station assignment.

Assets are in ETRS89 / UTM zone 32N (metres); stations are WGS84 lat/lon.
Stations are projected into the asset CRS so distances are plain Euclidean
metres, which is accurate to well under a percent at Danish latitudes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyproj import Transformer

ASSET_CRS = "EPSG:25832"
STATION_CRS = "EPSG:4326"


def stations_to_asset_crs(stations: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of `stations` with x, y columns in the asset CRS."""
    transformer = Transformer.from_crs(STATION_CRS, ASSET_CRS, always_xy=True)
    x, y = transformer.transform(stations["lon"].to_numpy(float), stations["lat"].to_numpy(float))
    return stations.assign(x=x, y=y)


def nearest_station(assets: pd.DataFrame, stations_xy: pd.DataFrame) -> pd.DataFrame:
    """The asset's station is the closest one by Euclidean distance in the
    asset CRS; on an exact tie the smallest station_id wins.

    Output columns: asset_id, station_id, distance_m.
    """
    stations = stations_xy.sort_values("station_id").reset_index(drop=True)
    dx = assets["x"].to_numpy(float)[:, None] - stations["x"].to_numpy(float)[None, :]
    dy = assets["y"].to_numpy(float)[:, None] - stations["y"].to_numpy(float)[None, :]
    dist = np.hypot(dx, dy)
    nearest = dist.argmin(axis=1)  # first minimum, i.e. smallest station_id on ties
    return pd.DataFrame(
        {
            "asset_id": assets["asset_id"].to_numpy(),
            "station_id": stations["station_id"].to_numpy()[nearest],
            "distance_m": dist[np.arange(len(assets)), nearest],
        }
    )
