# CLAUDE.md: working instructions for the Envira exposure case

Repository-specific instructions used with Claude Code during the two-hour case. Included in the submission as the brief asks. No private or employer configuration lives here.

## What we are building

Read `docs/CANDIDATE-BRIEF.md` first. It is the specification, and its definitions are binding:

- Local day: a calendar day in Europe/Copenhagen. Observation timestamps are UTC.
- Wet day: a local day with total precipitation of at least 20.0 mm at the asset's station.
- Worst 3-day accumulation: the highest total over three consecutive local calendar days. Consecutive means consecutive dates, not consecutive rows.
- Asset's station: the nearest station. Station rows carry validity dates, so the chosen policy is stated in DECISIONS.md.

Priority: a correct, runnable single-asset endpoint first. Then tests, README and Dockerfile. Backlog items only if they add clear value in the remaining time.

## Stack

- Python 3.12 managed by uv (`uv sync`, `uv run`).
- FastAPI and uvicorn for the API, pandas for loading and aggregation, pyproj for coordinate transformation, pytest for tests.
- One package `exposure/` with clear boundaries: `data.py` (load and clean), `geo.py` (CRS and nearest station), `metrics.py` (daily totals, wet days, worst 3-day window), `service.py` (join layer shared by the API and the CLI), `api.py` (FastAPI app), `cli.py` (CLI printing the same summary).
- Everything precomputed in memory at startup. No database unless there is a concrete reason.

## Data handling rules

- Treat the CSVs as source data. Profile before implementing: key uniqueness, value ranges and impossible values, time coverage and gaps, coordinate reference systems.
- Every cleaning rule is explicit, applied in one place (`data.py`), logged with counts at startup and written down in DECISIONS.md.
- Never let load order silently decide between conflicting rows.
- Business constants (the 20.0 mm threshold, the 3-day window) live in one place and are passed through, never repeated in other layers.

## Verification rules

- Establish that a number is right independently of the implementation: a small script that recomputes the exposure for a handful of assets in a different way (plain csv and zoneinfo, no pandas), plus tests on the business logic with hand-built inputs: the UTC to local midnight boundary, a missing calendar day inside a 3-day window, conflicting duplicate rows, impossible values such as negative precipitation.
- Run the tests and call the endpoint before claiming something works.

## Working method

- Commit small and often, with messages that say why.
- Keep the implementation small. Reject generated code that adds abstraction, configuration or features the brief did not ask for.
- Record every assumption in DECISIONS.md as it is made, not at the end.
- Time-box: check the clock at 30, 60 and 90 minutes and cut scope, not quality.
- Subagents may be used for parallel work (data profiling, independent verification, docs), each with a bounded task and a written result. The main session integrates and reviews every diff.

## Submission checklist

- README: how to run locally and with Docker, example requests.
- DECISIONS.md with Started and Stopped, then exactly the three headings from the brief, 10 to 20 lines, naming the AI tools used and one thing verified, changed or rejected.
- Nothing private or employer-specific in the repository.
