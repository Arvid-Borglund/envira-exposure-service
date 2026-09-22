"""Load the three CSVs and apply the cleaning rules.

Every cleaning rule lives here, is applied once and is logged with a count.
Load order never decides between conflicting rows: conflicts are excluded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

ASSET_COLUMNS = ["asset_id", "address", "x", "y", "asset_type", "insured_value_dkk"]
STATION_COLUMNS = ["station_id", "station_name", "lat", "lon"]
OBSERVATION_COLUMNS = ["station_id", "observed_at", "precip_mm"]


@dataclass(frozen=True)
class Dataset:
    assets: pd.DataFrame
    stations: pd.DataFrame
    observations: pd.DataFrame
    ambiguous_asset_ids: frozenset[str]
    cleaning: dict[str, int]


def clean_assets(raw: pd.DataFrame) -> tuple[pd.DataFrame, frozenset[str], dict[str, int]]:
    """An asset_id that occurs more than once is ambiguous: all its rows are
    excluded and the id is reported, so no row wins by load order."""
    if raw[ASSET_COLUMNS].isna().any().any():
        raise ValueError("assets.csv has missing values; the cleaning rules do not cover that")
    counts = raw["asset_id"].value_counts()
    ambiguous = frozenset(str(a) for a in counts[counts > 1].index)
    assets = raw.loc[~raw["asset_id"].isin(ambiguous), ASSET_COLUMNS].reset_index(drop=True)
    stats = {
        "assets_ambiguous_ids": len(ambiguous),
        "assets_rows_dropped": int(len(raw) - len(assets)),
    }
    return assets, ambiguous, stats


def clean_stations(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """A station is located at its current row, the one with no valid_to.
    Its whole observation history is attributed to that location."""
    valid_to = raw["valid_to"]
    is_current = valid_to.isna() | (valid_to.astype(str).str.strip() == "")
    current = raw.loc[is_current, STATION_COLUMNS]
    if not current["station_id"].is_unique:
        raise ValueError("stations.csv has more than one current row for a station")
    if set(current["station_id"]) != set(raw["station_id"]):
        raise ValueError("stations.csv has a station without a current row")
    row_counts = raw["station_id"].value_counts()
    stats = {"stations_relocated": int((row_counts > 1).sum())}
    return current.reset_index(drop=True), stats


def clean_observations(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Negative precipitation is a missing-value sentinel and is dropped first,
    so a sentinel never masks a valid reading. Then a (station_id, observed_at)
    pair with two different readings is a conflict and both rows are dropped;
    identical duplicate rows are collapsed to one."""
    obs = raw[OBSERVATION_COLUMNS].copy()
    obs["observed_at"] = pd.to_datetime(obs["observed_at"], utc=True, format="ISO8601").dt.as_unit("ns")
    obs["precip_mm"] = obs["precip_mm"].astype(float)
    if obs["precip_mm"].isna().any():
        raise ValueError("observations.csv has missing precip_mm; the cleaning rules do not cover that")

    negative = obs["precip_mm"] < 0
    obs = obs.loc[~negative]

    identical = obs.duplicated(subset=OBSERVATION_COLUMNS, keep="first")
    obs = obs.loc[~identical]

    conflicting = obs.duplicated(subset=["station_id", "observed_at"], keep=False)
    conflicting_pairs = obs.loc[conflicting, ["station_id", "observed_at"]].drop_duplicates()
    obs = obs.loc[~conflicting]

    stats = {
        "obs_negative_precip_dropped": int(negative.sum()),
        "obs_identical_duplicates_dropped": int(identical.sum()),
        "obs_conflicting_pairs_dropped": int(len(conflicting_pairs)),
        "obs_conflicting_rows_dropped": int(conflicting.sum()),
    }
    return obs.reset_index(drop=True), stats


def load_dataset(data_dir: Path) -> Dataset:
    """Read assets, stations and observations from `data_dir`, clean them and
    log what each rule removed."""
    data_dir = Path(data_dir)
    assets, ambiguous, asset_stats = clean_assets(pd.read_csv(data_dir / "assets.csv"))
    stations, station_stats = clean_stations(pd.read_csv(data_dir / "stations.csv"))
    observations, obs_stats = clean_observations(pd.read_csv(data_dir / "observations.csv"))

    unknown_stations = set(observations["station_id"]) - set(stations["station_id"])
    if unknown_stations:
        raise ValueError(f"observations reference unknown stations: {sorted(unknown_stations)}")

    cleaning = {**asset_stats, **station_stats, **obs_stats}
    for rule, count in cleaning.items():
        log.info("cleaning %s=%d", rule, count)
    log.info(
        "loaded %d assets (%d ambiguous ids excluded), %d stations, %d observations",
        len(assets), len(ambiguous), len(stations), len(observations),
    )
    return Dataset(assets, stations, observations, ambiguous, cleaning)
