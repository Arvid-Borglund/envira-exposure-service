"""Print the rainfall exposure summary for one asset: same numbers as the API.

Usage: python -m exposure.cli A-200975 [--json] [--data-dir PATH]
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def format_summary(e: dict) -> str:
    s, p = e["station"], e["period"]
    return "\n".join([
        f"Asset {e['asset_id']}: {e['address']} ({e['asset_type']}), insured {e['insured_value_dkk']:,} DKK",
        f"Nearest station: {s['station_id']} ({s['station_name']}), {s['distance_m'] / 1000:.1f} km away",
        f"Wet days: {e['wet_days']}  (local days, Europe/Copenhagen, with at least 20.0 mm)",
        f"Worst 3-day accumulation: {e['worst_3day_mm']:.1f} mm  ({e['worst_3day_start']} to {e['worst_3day_end']})",
        f"Period: {p['start']} to {p['end']}, {p['days_observed']} days observed",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m exposure.cli", description=__doc__.splitlines()[0])
    parser.add_argument("asset_id", help="asset id, for example A-200975")
    parser.add_argument("--json", action="store_true", help="print the exposure as JSON instead of text")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="directory with assets.csv, stations.csv and observations.csv "
                             "(default: $EXPOSURE_DATA_DIR, else the repo's data/)")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or Path(os.environ.get("EXPOSURE_DATA_DIR") or DEFAULT_DATA_DIR)

    # Cleaning counts are logged at INFO; keep them on stderr so stdout is only the summary.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")

    from exposure.service import AssetAmbiguous, AssetNotFound, build_index  # lazy so --help needs no data

    index = build_index(data_dir)
    try:
        exposure = index.exposure(args.asset_id.strip())
    except (AssetNotFound, AssetAmbiguous) as exc:
        print(f"error: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 1

    print(json.dumps(exposure, indent=2) if args.json else format_summary(exposure))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
