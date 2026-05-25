"""
download_boundaries.py
-----------------------
Downloads Kerala administrative boundary data (village + taluk level)
from https://github.com/geohacker/kerala and saves the filtered GeoJSON
files for our three districts into data/shapefiles/.

Usage
-----
    python download_boundaries.py                  # village level (default)
    python download_boundaries.py --level taluk    # taluk level
    python download_boundaries.py --level both     # save both

No sign-up, no API key.  License: ODbL (OpenStreetMap / datameet.org).

What it produces
----------------
    data/shapefiles/kerala_subdivisions.geojson    (the file shapefile_loader.py picks up)
    data/shapefiles/kerala_taluks.geojson          (if --level taluk or both)
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger(__name__)

# Project root = directory this script lives in
PROJECT_ROOT = Path(__file__).resolve().parent
SHAPEFILE_DIR = PROJECT_ROOT / "data" / "shapefiles"
SHAPEFILE_DIR.mkdir(parents=True, exist_ok=True)

REPO_URL = "https://github.com/geohacker/kerala.git"

TARGET_DISTRICTS = {
    "Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha",
    "Kottayam", "Idukki", "Ernakulam", "Thrissur", "Palakkad",
    "Malappuram", "Kozhikode", "Wayanad", "Kannur", "Kasaragod",
}

# Column names in the downloaded GeoJSONs
DISTRICT_COL = "DISTRICT"
VILLAGE_NAME_COL = "NAME"      # in village.geojson
TALUK_NAME_COL   = "TALUK"    # in taluk.geojson


def clone_repo(dest: Path) -> None:
    logger.info("Cloning geohacker/kerala (shallow)…")
    result = subprocess.run(
        ["git", "clone", "--depth=1", REPO_URL, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("git clone failed:\n%s", result.stderr)
        raise RuntimeError("Could not clone geohacker/kerala. Check internet connection.")
    logger.info("Clone complete.")


def filter_geojson(
    src: Path,
    name_col: str,
    out_path: Path,
    districts: set,
) -> int:
    """
    Read a GeoJSON, keep only features whose DISTRICT is in `districts`,
    and write a filtered copy to out_path.  Returns number of features kept.
    """
    with open(src) as f:
        gj = json.load(f)

    kept = [
        feat for feat in gj["features"]
        if feat["properties"].get(DISTRICT_COL, "") in districts
    ]

    # Normalise: ensure DISTRICT and NAME columns are present for shapefile_loader.py
    for feat in kept:
        props = feat["properties"]
        if "NAME" not in props:
            props["NAME"] = props.get(name_col, "Unknown")

    out_gj = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": kept,
    }
    with open(out_path, "w") as f:
        json.dump(out_gj, f)

    logger.info(
        "Written %d features → %s", len(kept), out_path.relative_to(PROJECT_ROOT)
    )
    return len(kept)


def print_summary(path: Path, label: str) -> None:
    with open(path) as f:
        gj = json.load(f)
    by_district: dict[str, int] = {}
    for feat in gj["features"]:
        d = feat["properties"].get(DISTRICT_COL, "Unknown")
        by_district[d] = by_district.get(d, 0) + 1

    print(f"\n{label} ({sum(by_district.values())} total)")
    print("-" * 40)
    for d, n in sorted(by_district.items()):
        print(f"  {d:<20} {n:>4} features")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Kerala boundary GeoJSONs.")
    parser.add_argument(
        "--level",
        choices=["village", "taluk", "both"],
        default="village",
        help="Boundary granularity (default: village)",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "kerala"
        clone_repo(repo)

        geojsons_dir = repo / "geojsons"

        if args.level in ("village", "both"):
            out = SHAPEFILE_DIR / "kerala_subdivisions.geojson"
            n = filter_geojson(
                geojsons_dir / "village.geojson",
                name_col=VILLAGE_NAME_COL,
                out_path=out,
                districts=TARGET_DISTRICTS,
            )
            print_summary(out, "Village-level boundaries (kerala_subdivisions.geojson)")

        if args.level in ("taluk", "both"):
            out = SHAPEFILE_DIR / "kerala_taluks.geojson"
            n = filter_geojson(
                geojsons_dir / "taluk.geojson",
                name_col=TALUK_NAME_COL,
                out_path=out,
                districts=TARGET_DISTRICTS,
            )
            print_summary(out, "Taluk-level boundaries (kerala_taluks.geojson)")

    print(f"\nFiles saved to: {SHAPEFILE_DIR}")
    print("\nYou're all set. Run 'python main.py' to start the API.")


if __name__ == "__main__":
    main()
