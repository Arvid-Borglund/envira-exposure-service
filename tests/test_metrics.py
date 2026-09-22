"""Business logic on hand-built inputs: local days, wet days, worst 3-day window."""

from datetime import date, datetime

import pandas as pd
import pytest

from exposure.metrics import (
    LOCAL_TZ,
    WET_DAY_THRESHOLD_MM,
    WINDOW_DAYS,
    StationExposure,
    daily_totals,
    exposure_by_station,
    station_exposure,
)


def observations(rows):
    """Observations frame shaped like data.clean_observations output: (station_id, iso_utc, mm)."""
    df = pd.DataFrame(rows, columns=["station_id", "observed_at", "precip_mm"])
    df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True)
    return df


def series(values: dict[date, float]) -> pd.Series:
    """Daily mm for one station, indexed by datetime.date."""
    return pd.Series(values, dtype="float64")


def test_brief_constants():
    assert WET_DAY_THRESHOLD_MM == 20.0
    assert WINDOW_DAYS == 3
    assert LOCAL_TZ == "Europe/Copenhagen"


def test_late_utc_evening_belongs_to_next_local_day_in_winter():
    out = daily_totals(observations([("S", "2025-03-01T23:00:00Z", 4.0)]))
    assert list(out["local_date"]) == [date(2025, 3, 2)]
    assert all(type(d) is date and not isinstance(d, datetime) for d in out["local_date"])


def test_cest_boundary_is_22_utc_in_summer():
    out = daily_totals(
        observations([("S", "2025-07-01T21:59:00Z", 1.0), ("S", "2025-07-01T23:00:00Z", 2.0)])
    )
    by_day = dict(zip(out["local_date"], out["precip_mm"]))
    assert by_day == {date(2025, 7, 1): 1.0, date(2025, 7, 2): 2.0}


def test_daily_totals_sums_slots_and_keeps_stations_apart():
    out = daily_totals(
        observations(
            [
                ("A", "2025-05-10T05:00:00Z", 1.0),
                ("A", "2025-05-10T11:00:00Z", 2.0),
                ("A", "2025-05-10T17:00:00Z", 3.0),
                ("B", "2025-05-10T05:00:00Z", 10.0),
            ]
        )
    )
    assert list(out.columns) == ["station_id", "local_date", "precip_mm"]
    rows = {(r.station_id, r.local_date): r.precip_mm for r in out.itertuples()}
    assert rows == {("A", date(2025, 5, 10)): 6.0, ("B", date(2025, 5, 10)): 10.0}


def test_wet_day_threshold_is_inclusive():
    result = station_exposure(
        series({date(2025, 1, 1): 20.0, date(2025, 1, 2): 19.9, date(2025, 1, 3): 25.0})
    )
    assert result.wet_days == 2
    assert isinstance(result.wet_days, int)  # not numpy int64: it must JSON-serialise
    assert isinstance(result.worst_window_mm, float)


def test_worst_window_is_over_consecutive_dates_not_rows():
    daily = series(
        {date(2025, 1, 1): 10.0, date(2025, 1, 2): 10.0, date(2025, 1, 5): 30.0, date(2025, 1, 6): 30.0}
    )
    result = station_exposure(daily)
    assert result.worst_window_mm == 60.0  # not 70: rows 2, 5 and 6 are not consecutive days
    assert (result.worst_window_end - result.worst_window_start).days == 2
    assert result.worst_window_start <= date(2025, 1, 5)
    assert result.worst_window_end >= date(2025, 1, 6)


def test_missing_day_inside_window_counts_as_zero():
    result = station_exposure(series({date(2025, 1, 1): 10.0, date(2025, 1, 3): 10.0}))
    assert result.worst_window_mm == 20.0
    assert (result.worst_window_start, result.worst_window_end) == (date(2025, 1, 1), date(2025, 1, 3))


def test_series_shorter_than_window_still_yields_a_window():
    one = station_exposure(series({date(2025, 1, 1): 5.0}))
    assert one.worst_window_mm == 5.0
    assert one.worst_window_start <= date(2025, 1, 1) <= one.worst_window_end
    assert (one.worst_window_end - one.worst_window_start).days <= 2

    two = station_exposure(series({date(2025, 1, 1): 5.0, date(2025, 1, 2): 7.0}))
    assert two.worst_window_mm == 12.0
    assert two.worst_window_start <= date(2025, 1, 1)
    assert two.worst_window_end >= date(2025, 1, 2)
    assert (two.worst_window_end - two.worst_window_start).days <= 2


def test_unsorted_input_gives_same_result_as_sorted():
    values = {date(2025, 2, d): float(mm) for d, mm in [(1, 3), (2, 25), (3, 8), (4, 0), (5, 40), (6, 1)]}
    sorted_result = station_exposure(series(dict(sorted(values.items()))))
    reversed_result = station_exposure(series(dict(reversed(sorted(values.items())))))
    assert reversed_result == sorted_result
    assert sorted_result.worst_window_mm == 48.0


def test_period_reflects_dates_present():
    result = station_exposure(
        series({date(2025, 3, 3): 1.0, date(2025, 3, 10): 2.0, date(2025, 3, 20): 0.0})
    )
    assert result.period_start == date(2025, 3, 3)
    assert result.period_end == date(2025, 3, 20)
    assert result.days_observed == 3


def test_empty_series_raises():
    with pytest.raises(ValueError):
        station_exposure(pd.Series(dtype="float64"))


def test_threshold_and_window_are_parameters_with_brief_defaults():
    daily = series({date(2025, 1, 1): 6.0, date(2025, 1, 2): 4.0, date(2025, 1, 3): 21.0})
    assert station_exposure(daily).wet_days == 1
    assert station_exposure(daily, threshold_mm=5.0).wet_days == 2
    assert station_exposure(daily, window_days=1).worst_window_mm == 21.0


def test_exposure_by_station_returns_one_entry_per_station():
    result = exposure_by_station(
        observations(
            [
                ("A", "2025-05-10T05:00:00Z", 25.0),
                ("B", "2025-05-10T05:00:00Z", 5.0),
                ("B", "2025-05-11T05:00:00Z", 30.0),
            ]
        )
    )
    assert set(result) == {"A", "B"}
    assert all(isinstance(v, StationExposure) for v in result.values())
    assert (result["A"].wet_days, result["A"].worst_window_mm) == (1, 25.0)
    assert (result["B"].wet_days, result["B"].worst_window_mm) == (1, 35.0)
