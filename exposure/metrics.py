"""Business metrics: daily totals, wet days and the worst 3-day accumulation.

The business constants live here and only here; every other layer receives
them as arguments.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

WET_DAY_THRESHOLD_MM = 20.0
WINDOW_DAYS = 3
LOCAL_TZ = "Europe/Copenhagen"

# Totals are compared at micrometre precision so that float noise in a sum of
# 0.1 mm readings can never flip a threshold decision.
_COMPARE_DECIMALS = 6


@dataclass(frozen=True)
class StationExposure:
    wet_days: int
    worst_window_mm: float
    worst_window_start: date
    worst_window_end: date
    period_start: date
    period_end: date
    days_observed: int


def daily_totals(observations: pd.DataFrame, tz: str = LOCAL_TZ) -> pd.DataFrame:
    """A local day is the calendar date of the observation in `tz`; its total is
    the sum of the valid observations on that date. Days without any valid
    observation do not appear.

    Output columns: station_id, local_date (datetime.date), precip_mm.
    """
    local_date = observations["observed_at"].dt.tz_convert(tz).dt.date
    return (
        observations.assign(local_date=local_date)
        .groupby(["station_id", "local_date"], as_index=False, sort=True)["precip_mm"]
        .sum()
    )


def station_exposure(
    daily: pd.Series,
    *,
    threshold_mm: float = WET_DAY_THRESHOLD_MM,
    window_days: int = WINDOW_DAYS,
) -> StationExposure:
    """Exposure for one station from its daily totals (mm indexed by date).

    A wet day is an observed day with total >= threshold. The worst window is
    the highest total over `window_days` consecutive calendar dates between the
    first and last observed date; dates with no observation count as 0 mm. On
    ties the earliest window wins.
    """
    if daily.empty:
        raise ValueError("cannot compute exposure from an empty series of daily totals")
    observed = (
        pd.Series(daily.to_numpy(dtype=float), index=pd.to_datetime(list(daily.index)))
        .sort_index()
        .round(_COMPARE_DECIMALS)
    )
    period_start, period_end = observed.index[0], observed.index[-1]

    all_days = pd.date_range(period_start, period_end, freq="D")
    filled = observed.reindex(all_days, fill_value=0.0)
    window_sum = filled.rolling(window_days, min_periods=1).sum().round(_COMPARE_DECIMALS)
    window_end = window_sum.idxmax()  # first occurrence on ties
    window_start = max(window_end - pd.Timedelta(days=window_days - 1), period_start)

    return StationExposure(
        wet_days=int((observed >= threshold_mm).sum()),
        worst_window_mm=float(window_sum[window_end]),
        worst_window_start=window_start.date(),
        worst_window_end=window_end.date(),
        period_start=period_start.date(),
        period_end=period_end.date(),
        days_observed=int(len(observed)),
    )


def exposure_by_station(
    observations: pd.DataFrame,
    *,
    tz: str = LOCAL_TZ,
    threshold_mm: float = WET_DAY_THRESHOLD_MM,
    window_days: int = WINDOW_DAYS,
) -> dict[str, StationExposure]:
    """StationExposure for every station present in the cleaned observations."""
    daily = daily_totals(observations, tz=tz)
    return {
        station_id: station_exposure(
            group.set_index("local_date")["precip_mm"],
            threshold_mm=threshold_mm,
            window_days=window_days,
        )
        for station_id, group in daily.groupby("station_id", sort=True)
    }
