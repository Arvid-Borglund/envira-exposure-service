"""The join layer shared by the API and the CLI.

Everything is precomputed once at startup: each asset is joined with its
nearest station and that station's exposure, and the result is kept as a
ready-to-serialise dict per asset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from exposure.data import load_dataset
from exposure.geo import nearest_station, stations_to_asset_crs
from exposure.metrics import StationExposure, exposure_by_station

RANKING = "worst_3day_mm desc, wet_days desc"


class AssetNotFound(KeyError):
    """No unambiguous asset with this id."""

    def __str__(self) -> str:  # KeyError would wrap the message in quotes
        return str(self.args[0]) if self.args else ""


class AssetAmbiguous(ValueError):
    """The id appears more than once in assets.csv with conflicting attributes."""


@dataclass
class ExposureIndex:
    rows: dict[str, dict]  # asset_id -> single-asset dict, insertion order = ranking
    ambiguous_counts: dict[str, int]  # ambiguous asset_id -> number of source rows
    asset_types: list[str]
    n_stations: int
    n_observations: int
    cleaning: dict[str, int] = field(default_factory=dict)

    def exposure(self, asset_id: str) -> dict:
        """The single-asset exposure dict; raises AssetNotFound / AssetAmbiguous."""
        if asset_id in self.ambiguous_counts:
            raise AssetAmbiguous(
                f"asset id {asset_id} appears {self.ambiguous_counts[asset_id]} times "
                "in assets.csv with conflicting attributes"
            )
        try:
            return self.rows[asset_id]
        except KeyError:
            raise AssetNotFound(f"unknown asset id {asset_id}") from None

    def portfolio(self, asset_type: str | None = None, ids: list[str] | None = None) -> dict:
        """Assets selected by type or by id, ranked worst first (RANKING, then
        asset_id). Unknown and ambiguous ids are skipped and reported."""
        skipped = {"unknown": [], "ambiguous": []}
        if ids is not None:
            wanted = set(ids)
            for asset_id in ids:
                if asset_id in self.ambiguous_counts:
                    skipped["ambiguous"].append(asset_id)
                elif asset_id not in self.rows:
                    skipped["unknown"].append(asset_id)
            selected = [row for row in self.rows.values() if row["asset_id"] in wanted]
        else:
            selected = [row for row in self.rows.values() if row["asset_type"] == asset_type]
        assets = [{**row, "rank": rank} for rank, row in enumerate(selected, start=1)]
        return {"assets": assets, "skipped": skipped}

    def summary(self) -> dict:
        return {
            "assets": len(self.rows),
            "ambiguous_assets": len(self.ambiguous_counts),
            "stations": self.n_stations,
            "observations": self.n_observations,
            "cleaning": self.cleaning,
        }


def _asset_row(asset: pd.Series, exposure: StationExposure) -> dict:
    """The single-asset JSON. Millimetres and metres are rounded to one decimal
    here and nowhere else."""
    return {
        "asset_id": str(asset["asset_id"]),
        "address": str(asset["address"]),
        "asset_type": str(asset["asset_type"]),
        "insured_value_dkk": int(asset["insured_value_dkk"]),
        "station": {
            "station_id": str(asset["station_id"]),
            "station_name": str(asset["station_name"]),
            "distance_m": round(float(asset["distance_m"]), 1),
        },
        "wet_days": exposure.wet_days,
        "worst_3day_mm": round(exposure.worst_window_mm, 1),
        "worst_3day_start": exposure.worst_window_start.isoformat(),
        "worst_3day_end": exposure.worst_window_end.isoformat(),
        "period": {
            "start": exposure.period_start.isoformat(),
            "end": exposure.period_end.isoformat(),
            "days_observed": exposure.days_observed,
        },
    }


def build_index(data_dir: Path) -> ExposureIndex:
    """Load and clean the data, assign each asset its nearest station and
    precompute every asset's exposure."""
    data_dir = Path(data_dir)
    dataset = load_dataset(data_dir)
    stations_xy = stations_to_asset_crs(dataset.stations)
    nearest = nearest_station(dataset.assets, stations_xy)
    joined = dataset.assets.merge(nearest, on="asset_id", validate="one_to_one").merge(
        dataset.stations[["station_id", "station_name"]], on="station_id", validate="many_to_one"
    )
    by_station = exposure_by_station(dataset.observations)

    rows = [_asset_row(asset, by_station[asset["station_id"]]) for _, asset in joined.iterrows()]
    rows.sort(key=lambda r: (-r["worst_3day_mm"], -r["wet_days"], r["asset_id"]))

    # The source row count per ambiguous id is only needed for the 409 message,
    # so it is read from the id column alone rather than widening Dataset.
    raw_ids = pd.read_csv(data_dir / "assets.csv", usecols=["asset_id"])["asset_id"]
    counts = raw_ids.value_counts()
    ambiguous_counts = {str(a): int(counts[a]) for a in dataset.ambiguous_asset_ids}

    return ExposureIndex(
        rows={row["asset_id"]: row for row in rows},
        ambiguous_counts=ambiguous_counts,
        asset_types=sorted(set(dataset.assets["asset_type"].astype(str))),
        n_stations=len(dataset.stations),
        n_observations=len(dataset.observations),
        cleaning=dict(dataset.cleaning),
    )
