"""Independent recomputation of heavy-rainfall exposure, standard library only.

Deliberately built a different way from the service: plain csv + zoneinfo instead
of pandas, exact Decimal sums instead of float sums, and the asset is transformed
to WGS84 and compared with haversine distances instead of transforming stations
to UTM and using planar distance. pyproj is used only for the CRS transform.

Usage:
  uv run python scripts/verify_exposure.py A-200975 A-206420
  uv run python scripts/verify_exposure.py --all-random 20
  uv run python scripts/verify_exposure.py A-200975 --compare-url http://localhost:8000
"""
import argparse, csv, json, math, random, sys, urllib.error, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
from pyproj import Transformer

DATA = Path(__file__).resolve().parent.parent / "data"
TZ = ZoneInfo("Europe/Copenhagen")
WET_MM = Decimal("20.0")
WINDOW_DAYS = 3
EARTH_RADIUS_M = 6371008.8
TO_WGS84 = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)


def load_assets():
    """{asset_id: (x, y)} for unambiguous ids, plus the set of ambiguous ids."""
    rows = defaultdict(list)
    with open(DATA / "assets.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["asset_id"]].append(tuple(sorted(r.items())))
    assets, ambiguous = {}, set()
    for aid, rs in rows.items():
        if len(set(rs)) > 1:
            ambiguous.add(aid)
        else:
            r = dict(rs[0])
            assets[aid] = (float(r["x"]), float(r["y"]))
    return assets, ambiguous


def load_stations(current=True):
    """{station_id: (lat, lon)}: the row with empty valid_to, or with current=False the earliest row."""
    stations = {}
    with open(DATA / "stations.csv", newline="") as f:
        for r in sorted(csv.DictReader(f), key=lambda r: r["valid_from"]):
            if current and r["valid_to"].strip() != "":
                continue
            stations.setdefault(r["station_id"], (float(r["lat"]), float(r["lon"])))
    return stations


def load_daily_totals(local=True):
    """{station_id: {date: Decimal mm}} after cleaning; local=False groups by UTC date."""
    slots = defaultdict(list)
    with open(DATA / "observations.csv", newline="") as f:
        for r in csv.DictReader(f):
            v = Decimal(r["precip_mm"])
            if v >= 0:  # -999 / -9999 sentinels are not measurements
                slots[(r["station_id"], r["observed_at"])].append(v)
    daily = defaultdict(lambda: defaultdict(Decimal))
    for (sid, ts), vals in slots.items():
        if len(set(vals)) > 1:  # conflicting duplicate: neither value is trusted
            continue
        utc = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        day = utc.astimezone(TZ).date() if local else utc.date()
        daily[sid][day] += vals[0]
    return daily


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def rank_stations(x, y, stations):
    """[(distance_m, station_id), ...] nearest first."""
    lon, lat = TO_WGS84.transform(x, y)
    return sorted((haversine_m(lat, lon, slat, slon), sid) for sid, (slat, slon) in stations.items())


def worst_window(daily):
    """(total, start_date) of the wettest run of WINDOW_DAYS consecutive dates; first wins ties."""
    first, last = min(daily), max(daily)
    best, best_start, d = Decimal(-1), None, first
    while d == first or d + timedelta(days=WINDOW_DAYS - 1) <= last:
        total = sum(daily.get(d + timedelta(days=i), Decimal(0)) for i in range(WINDOW_DAYS))
        if total > best:
            best, best_start = total, d
        d += timedelta(days=1)
    return best, best_start


def exposure(aid, assets, ambiguous, stations, daily):
    if aid in ambiguous:
        return {"asset_id": aid, "status": "ambiguous"}
    if aid not in assets:
        return {"asset_id": aid, "status": "unknown"}
    ranked = rank_stations(*assets[aid], stations)
    dist, sid = ranked[0]
    days = daily[sid]
    total, start = worst_window(days)
    return {
        "asset_id": aid, "station_id": sid, "distance_m": round(dist, 1),
        "wet_days": sum(1 for mm in days.values() if mm >= WET_MM),
        "worst_3day_mm": float(round(total, 1)),
        "worst_3day_start": start.isoformat(),
        "worst_3day_end": (start + timedelta(days=WINDOW_DAYS - 1)).isoformat(),
        "period_start": min(days).isoformat(), "period_end": max(days).isoformat(),
        "days_observed": len(days), "_runner_up": [ranked[1][1], round(ranked[1][0], 1)],
    }


def flatten(obj, prefix=""):
    out = {}
    for k, v in (obj or {}).items():
        out.update(flatten(v, f"{prefix}{k}.") if isinstance(v, dict) else {f"{prefix}{k}": v})
    return out


ALIASES = {  # (last path segment, substring the full dotted path must contain) per verifier field
    "station_id": (("station_id", ""), ("id", "station")),
    "distance_m": (("distance_m", ""),),
    "wet_days": (("wet_days", ""), ("wet_day_count", "")),
    "worst_3day_mm": (("worst_3day_mm", ""), ("total_mm", "worst"), ("mm", "worst")),
    "worst_3day_start": (("worst_3day_start", ""), ("start", "worst")),
    "worst_3day_end": (("worst_3day_end", ""), ("end", "worst")),
    "period_start": (("period_start", ""), ("start", "period")),
    "period_end": (("period_end", ""), ("end", "period")),
    "days_observed": (("days_observed", ""), ("days", "period")),
}


TOLERANCE = {  # haversine on a sphere underestimates east-west distances at 56 N by up to ~0.35 %
    # (ellipsoid flattening); the UTM scale factor adds < 0.01 %. mm are rounded to 1 dp.
    "distance_m": lambda got, want: abs(got - want) <= 0.005 * want,
    "worst_3day_mm": lambda got, want: abs(got - want) <= 0.05,
}


def pick(flat, field):
    for name, must in ALIASES[field]:
        for key, value in flat.items():
            if key.split(".")[-1] == name and must in key:
                return value
    return None


def compare(mine, base_url):
    """Print a per-field diff against the API; return True when everything matches."""
    aid = mine["asset_id"]
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/assets/{aid}/exposure", timeout=15) as resp:
            api, status = json.load(resp), resp.status
    except urllib.error.HTTPError as e:
        api, status = None, e.code
    if "status" in mine:
        print(f"{aid}: verifier says {mine['status']}, API HTTP {status}")
        return status != 200
    if api is None:
        print(f"{aid}: API HTTP {status}, expected 200")
        return False
    flat, ok = flatten(api), True
    for field in ALIASES:
        want, got = mine[field], pick(flat, field)
        rule = TOLERANCE.get(field)
        same = rule(got, want) if rule and isinstance(got, (int, float)) else str(got) == str(want)
        if not same:
            ok = False
            note = f"  (runner-up here: {mine['_runner_up']})" if field == "station_id" else ""
            print(f"{aid}: {field}: verifier={want!r} api={got!r}{note}")
    print(f"{aid}: {'OK' if ok else 'MISMATCH'}")
    if not ok:
        print(f"  api fields seen: {sorted(flat)}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asset_ids", nargs="*")
    ap.add_argument("--all-random", type=int, metavar="N", help="N random unique asset ids, seed 1")
    ap.add_argument("--compare-url", metavar="URL", help="diff against GET URL/assets/{id}/exposure")
    args = ap.parse_args()
    assets, ambiguous = load_assets()
    ids = list(args.asset_ids)
    if args.all_random:
        ids += random.Random(1).sample(sorted(set(assets) | ambiguous), args.all_random)
    if not ids:
        ap.error("give asset ids or --all-random N")
    stations, daily = load_stations(), load_daily_totals()
    all_ok = True
    for aid in ids:
        mine = exposure(aid, assets, ambiguous, stations, daily)
        if args.compare_url:
            all_ok &= compare(mine, args.compare_url)
        else:
            print(json.dumps({k: v for k, v in mine.items() if not k.startswith("_")}))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
