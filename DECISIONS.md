Started: 2026-09-22 10:25 CEST
Stopped: TBD

## What I built

## What I deliberately did not build, and why

## What I would do first with another day

<!-- draft notes for the orchestrator, delete before submission

Data and cleaning (all applied in exposure/data.py, logged with counts at startup):
- assets.csv x/y are EPSG:25832 (UTM 32N); stations.csv lat/lon are WGS84 (EPSG:4326). Reconciled with pyproj; distances are computed in metres in EPSG:25832.
- 40 asset ids appear twice with conflicting attributes. They are treated as ambiguous and the endpoint returns 409 for them; load order never picks a winner.
- 3 stations relocated 8-11 km mid-period (DK1560, DK1595, DK1665), visible as multiple rows with validity dates. Nearest station uses the station's current location and its full observation history, so one asset maps to one station for the whole period.
- 5285 observation rows carry sentinel precipitation (-999 / -9999) and are dropped.
- 200 duplicated (station, timestamp) pairs have conflicting precipitation values and are dropped entirely rather than resolved by load order.
- Values above 100 mm per 6 h (max 235.1) are kept: high but not impossible, and no rule in the brief excludes them.
- A 23:00Z observation belongs to the next local day (Europe/Copenhagen is UTC+1 or +2).
- A missing calendar day inside a 3-day window counts as 0 mm; windows are over consecutive dates, not consecutive rows.
- Portfolio ranking: worst 3-day accumulation desc, then wet days desc.

AI tooling:
- Claude Code with Fable 5.1. The main session orchestrated five parallel subagents in git worktrees: core package, tests, independent verification script (plain csv + zoneinfo, no pandas), docs and Docker, UI and CLI. Every diff was reviewed and integrated by the main session.
- One thing verified / changed / rejected: TBD (fill in; e.g. the verify script vs the API for A-200975 and A-206420, or a rejected generated abstraction).

-->
