# Envira practical test

## Exposure service

**Two hours of your time, followed by a 30-minute call with us.**

Thanks for getting this far. This task is intended to resemble a real morning at Envira: real-shaped data, more possible work than fits in the time, and decisions to make about what actually matters.

## Before you start

**Use the AI tooling you normally use.** We expect you to. Every engineer here works this way, and a test that pretended otherwise would tell us very little. You remain responsible for everything you submit.

If your normal setup uses repository-specific AI instructions such as `CLAUDE.md`, `AGENTS.md` or `.cursorrules`, include the ones you actually used. Do not include private or employer-specific global configuration.

**Work for a maximum of two hours.** Choose any two-hour block before the submission deadline. Record your start and stop time in `DECISIONS.md`. This is honour-based; the live walkthrough is more important to us than policing the clock.

**Keep a real git history.** Commit as you go rather than squashing everything into one final commit. We use the history as context, not as a stopwatch.

**There is more in this brief than fits in two hours. That is deliberate.** Your priority is a correct, runnable single-asset exposure endpoint. After that, choose what is worth adding. A small solution that works and is well understood will beat a large half-working one.

**If something is ambiguous or looks wrong, use your judgement.** Make a reasonable assumption, implement what you think is right, and state the assumption briefly. You may also ask us a question during the exercise.

---

## The problem

Envira prices climate risk on individual buildings for Danish insurers and banks. An underwriter looking at a property wants to know, quickly: how exposed is this asset to heavy rainfall, and how does it compare with the rest of the book?

You have a set of insured assets and a set of weather stations with an observation history. We would like a small service that answers that question.

---

## The data: `./data`

| file | rows | what it is |
|---|---:|---|
| `assets.csv` | ~5,000 | insured properties: id, address, coordinates, type, insured value |
| `stations.csv` | ~120 | weather stations: id, name, coordinates, validity dates |
| `observations.csv` | ~260,000 | 6-hourly precipitation and temperature observations, covering Jan 2025 through Jun 2026 in local-day terms |

Two things worth knowing before you start:

- **`assets.csv` and `stations.csv` do not use the same coordinate reference system.** Working out what they are and reconciling them is part of the task.
- **The files have not been cleaned for you.** Treat them as source data rather than assuming every row is valid or unique.

---

## Definitions

- **Local day**: a calendar day in `Europe/Copenhagen`.
- **Wet day**: a local day on which total precipitation at the asset's station is at least **20.0 mm**.
- **Worst 3-day accumulation**: the highest total precipitation over any **three consecutive local calendar days** in the period.
- **An asset's station**: the weather station closest to it. If the station data makes this definition ambiguous over time, make and document a reasonable assumption.

---

## What we would like

Start with the first item. Everything after that is a backlog. Decide how far to go.

1. **Core:** `GET /assets/{asset_id}/exposure` returning the asset's station, distance to it, wet-day count, worst 3-day accumulation, and the period covered.
2. `GET /portfolio/exposure` for a selection of assets, by type or by a list of ids. Return the same exposure measures and a useful ordering. There is deliberately no prescribed single "exposure score"; choose a sensible ranking and document it.
3. A simple page where a non-technical user can type an asset id and see the answer.
4. A `Dockerfile`, and a compose file if useful, so the service can be started on a known port with a simple command.
5. Tests.
6. Load the data into Postgres/PostGIS on startup rather than reading CSV files on every request.
7. A caching layer where it is actually useful.
8. A small CLI that prints the same exposure summary for a given asset id.

You are not expected to finish all eight items.

---

## What to send us

**The repository**, however far you got. A zip or a link to a private repository is fine.

**`DECISIONS.md`**, starting with:

```text
Started: YYYY-MM-DD HH:MM TZ
Stopped: YYYY-MM-DD HH:MM TZ
```

and then exactly these three headings:

- **What I built**
- **What I deliberately did not build, and why**
- **What I would do first with another day**

Keep it short, ideally 10 to 20 lines. Somewhere in those sections, briefly mention which AI tools you used and one thing you specifically verified, changed or rejected rather than simply accepting generated output.

---

## The call

Thirty minutes, screen shared. You will show us the service running, we will ask about parts of the code, and we will ask you to make one small change while we watch.

Use your normal working setup for the call: editor, terminal and AI tools included.

There is no trick to prepare for. We want to see how you understand, verify and change what you built.
