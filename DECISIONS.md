Started: 2026-09-22 10:25 CEST
Stopped: 2026-09-22 10:49 CEST

## What I built

- All of the backlog except Postgres and a cache: single-asset and portfolio endpoints, a lookup page, a CLI, a Dockerfile plus compose, 32 tests, a standard-library verifier and a two-job CI. Everything is precomputed in memory at startup, in about half a second.
- Cleaning in one place, logged with counts: 40 asset ids occur twice with conflicting attributes and answer 409; 5285 sentinel readings (-999/-9999) are dropped; 200 duplicated observation pairs with different readings are dropped entirely, never resolved by load order; readings above 100 mm per 6 h are kept.
- Assets are EPSG:25832 and stations WGS84; stations are projected into the asset CRS and distances are planar metres. Three stations moved 8-11 km mid-period: the nearest station uses the current location and the full history (116 assets would map differently with the old one).
- A 23:00Z observation belongs to the next local day, which changes the wet-day count for 107 of 120 stations. Missing dates inside a 3-day window count as 0. Portfolio ranking: worst 3-day accumulation desc, then wet days desc, then asset id.
- AI tooling: Claude Code with Fable 5.1. The main session profiled the data and wrote the cleaning policy and a module contract, then ran six subagents in git worktrees (core, tests, verifier, docs and Docker, page and CLI, CI) and reviewed and merged every branch.
- Changed rather than accepted: the generated verifier claimed its haversine distances would match the planar UTM distances within 0.1 % and failed on three of eight assets at 0.23-0.31 %. The gap is the spherical-earth approximation at 56 N, not the service, so I corrected the comment and the tolerance to 0.5 %. Every other field matched exactly on all sampled assets.

## What I deliberately did not build, and why

- Postgres/PostGIS and a cache: 5000 assets and 255k observations build into an index in under a second, so a database would add operations without adding correctness.
- A weighted exposure score: any weighting is a pricing decision, so the ranking uses the two measures the brief defines.
- Time-varying station assignment for the relocated stations: documented instead, given the time box.

## What I would do first with another day

- Use the insured value as the ranking tiebreak and show it in the portfolio; ties are common because exposure is per station.
- Settle with the domain owners whether conflicting duplicate readings should be excluded (now) or resolved conservatively with the maximum.
- Per-period nearest station for the three relocated stations, since 116 assets are affected.
