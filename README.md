# Envira exposure service

A small HTTP service that answers how exposed an insured asset is to heavy
rainfall. For each asset it finds the nearest weather station, aggregates that
station's 6-hourly observations into local calendar days, and reports the wet
days and the worst 3-day accumulation over the observed period. The CSV files
in `data/` are cleaned and precomputed in memory at startup (a few seconds);
the startup log prints how many rows each cleaning rule touched.

## Run locally

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

    uv sync
    uv run uvicorn exposure.api:app --port 8000

The data directory defaults to `data/` in the repository; set
`EXPOSURE_DATA_DIR` to point elsewhere.

## Run with Docker

    docker build -t envira-exposure .
    docker run --rm -p 8000:8000 envira-exposure

or, with compose (same image, same port, plus a healthcheck on `/health`):

    docker compose up --build

On a Docker install without the compose plugin, the standalone `docker-compose up --build` does the same.

## Endpoints

| Method and path | What it returns |
|---|---|
| `GET /assets/{asset_id}/exposure` | Exposure for one asset. 404 for an unknown id, 409 for an id that appears more than once in the source data with conflicting attributes. |
| `GET /portfolio/exposure?asset_type=residential` or `?ids=A-200975,A-206420` | The same measures for a selection of assets, ordered by worst 3-day accumulation (desc), then wet days (desc). |
| `GET /health` | Liveness check. |
| `GET /` | A simple page where a non-technical user can type an asset id. |
| `GET /docs` | FastAPI's generated API documentation. |

Valid asset types: `residential`, `commercial`, `industrial`, `public`, `agricultural`.

    curl http://localhost:8000/assets/A-200975/exposure
    curl "http://localhost:8000/portfolio/exposure?asset_type=residential"
    curl "http://localhost:8000/portfolio/exposure?ids=A-200975,A-206420"

Example single-asset response:
    {
      "asset_id": "A-200975",
      "address": "Lindevej 1",
      "asset_type": "industrial",
      "insured_value_dkk": 14707000,
      "station": {"station_id": "DK1469", "station_name": "Station DK1469", "distance_m": 10470.5},
      "wet_days": 26,
      "worst_3day_mm": 72.5,
      "worst_3day_start": "2026-01-13",
      "worst_3day_end": "2026-01-15",
      "period": {"start": "2025-01-01", "end": "2026-06-30", "days_observed": 546}
    }

## Definitions

Taken from the brief (`docs/CANDIDATE-BRIEF.md`) and binding for the implementation:

- Local day: a calendar day in `Europe/Copenhagen`; observation timestamps are UTC.
- Wet day: a local day with total precipitation of at least 20.0 mm at the asset's station.
- Worst 3-day accumulation: the highest total over three consecutive local calendar dates (not rows).
- Asset's station: the nearest station; the policy for stations with validity dates is in `DECISIONS.md`.

## Verify

    uv run pytest -q
    uv run python scripts/verify_exposure.py A-200975 A-206420
    uv run python scripts/verify_exposure.py A-200975 A-206420 --compare-url http://localhost:8000

The script recomputes the exposure with plain `csv` and `zoneinfo` (no pandas)
and, with `--compare-url`, checks the running service against it.

## Layout

- `exposure/data.py`: load and clean the CSV files; every cleaning rule lives here and is logged with counts.
- `exposure/geo.py`: coordinate reference systems and nearest-station lookup.
- `exposure/metrics.py`: daily totals, wet days, worst 3-day window.
- `exposure/service.py`: join layer shared by the API and the CLI.
- `exposure/api.py`: the FastAPI app (`exposure.api:app`).
- `exposure/cli.py`: `uv run python -m exposure.cli A-200975` prints the same summary.
- `exposure/static/index.html`: the page served at `/`.
- `scripts/verify_exposure.py`: independent recomputation, see Verify.
- `tests/`: pytest suite.

Assumptions and data decisions: `DECISIONS.md`. The task: `docs/CANDIDATE-BRIEF.md`.
