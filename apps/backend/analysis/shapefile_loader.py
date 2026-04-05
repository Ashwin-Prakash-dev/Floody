"""
analysis/shapefile_loader.py
-----------------------------
Loads and clips subdivision boundaries for the three Kerala districts.

Boundary data source
--------------------
Run download_boundaries.py once to populate data/shapefiles/:

    python download_boundaries.py          # village level (recommended, 234 features)
    python download_boundaries.py --level taluk   # 14 taluks across 3 districts

This downloads from https://github.com/geohacker/kerala (ODbL license,
Census 2011 base, village + taluk level).  Column names in that data:
    DISTRICT  – district name  (e.g. "Idukki", "Wayanad", "Ernakulam")
    NAME      – village name
    TALUK     – taluk name (in taluk.geojson only; normalised to NAME here)

Supported file layouts in data/shapefiles/
------------------------------------------
  A) kerala_subdivisions.geojson   ← produced by download_boundaries.py
  B) kerala_taluks.geojson         ← produced by download_boundaries.py --level taluk
  C) Per-district: idukki.geojson, wayanad.geojson, ernakulam.geojson
  D) Shapefiles: kerala_subdivisions.shp, etc.

Falls back to a synthetic grid if nothing is found (test mode).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np
from shapely.geometry import box

from config.settings import (
    DISTRICT_BOUNDS,
    OUTPUT_CRS,
    SHAPEFILE_DIR,
    SHAPEFILE_DISTRICT_COL,
    SHAPEFILE_SUBDIV_COL,
)

logger = logging.getLogger(__name__)

# Candidate combined-file names (checked in order).
# kerala_subdivisions.geojson is produced by download_boundaries.py (village level).
# kerala_taluks.geojson is the coarser taluk-level alternative.
_COMBINED_CANDIDATES = [
    "kerala_subdivisions.geojson",   # village-level  (download_boundaries.py default)
    "kerala_taluks.geojson",         # taluk-level    (download_boundaries.py --level taluk)
    "kerala_subdivisions.shp",       # legacy shapefile support
    "kerala_panchayats.shp",
    "kerala_taluks.shp",
    "subdivisions.shp",
]


def _find_shapefile(district: str) -> Optional[Path]:
    """Return the path to the best available boundary file for a district."""
    # 1. Per-district GeoJSON or shapefile
    for ext in (".geojson", ".shp"):
        per_district = SHAPEFILE_DIR / f"{district}{ext}"
        if per_district.exists():
            return per_district

    # 2. Combined file (GeoJSON preferred over shapefile)
    for name in _COMBINED_CANDIDATES:
        combined = SHAPEFILE_DIR / name
        if combined.exists():
            return combined

    return None


def _synthetic_grid(district: str, n: int = 16) -> gpd.GeoDataFrame:
    """
    Generate a regular n×n grid over the district bbox for testing
    when no real shapefile is available.
    """
    bbox = DISTRICT_BOUNDS[district]["bbox"]   # [W, S, E, N]
    w, s, e, n = bbox
    cols = rows = int(np.sqrt(n))

    lon_step = (e - w) / cols
    lat_step = (n - s) / rows

    geoms, names, districts = [], [], []
    idx = 1
    for r in range(rows):
        for c in range(cols):
            x0 = w + c * lon_step
            y0 = s + r * lat_step
            geoms.append(box(x0, y0, x0 + lon_step, y0 + lat_step))
            names.append(f"{district.capitalize()} Cell {idx:02d}")
            districts.append(DISTRICT_BOUNDS[district]["display"])
            idx += 1

    gdf = gpd.GeoDataFrame(
        {SHAPEFILE_DISTRICT_COL: districts, SHAPEFILE_SUBDIV_COL: names},
        geometry=geoms,
        crs=OUTPUT_CRS,
    )
    logger.warning(
        "No shapefile found for '%s'. Using synthetic %d-cell grid for testing.", district, len(gdf)
    )
    return gdf


def load_subdivisions(district: str) -> gpd.GeoDataFrame:
    """
    Load subdivision polygons for a district.

    Returns a GeoDataFrame in EPSG:4326 with at least:
      - SHAPEFILE_DISTRICT_COL column
      - SHAPEFILE_SUBDIV_COL column
      - geometry column
    """
    shp_path = _find_shapefile(district)

    if shp_path is None:
        return _synthetic_grid(district)

    logger.info("Loading shapefile: %s", shp_path)
    gdf = gpd.read_file(shp_path)

    # Reproject to WGS-84 if needed
    if gdf.crs is None:
        logger.warning("Shapefile has no CRS; assuming EPSG:4326.")
        gdf = gdf.set_crs(OUTPUT_CRS)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(OUTPUT_CRS)

    # Validate required columns
    missing = []
    for col in (SHAPEFILE_DISTRICT_COL, SHAPEFILE_SUBDIV_COL):
        if col not in gdf.columns:
            missing.append(col)
    if missing:
        raise KeyError(
            f"Shapefile '{shp_path}' is missing columns: {missing}. "
            f"Update SHAPEFILE_DISTRICT_COL / SHAPEFILE_SUBDIV_COL in config/settings.py."
        )

    # Clip to district bounding box
    bbox = DISTRICT_BOUNDS[district]["bbox"]
    clip_box = box(*bbox)
    gdf = gdf[gdf.geometry.intersects(clip_box)].copy()
    gdf.geometry = gdf.geometry.intersection(clip_box)
    gdf = gdf[~gdf.geometry.is_empty].reset_index(drop=True)

    # Optionally filter by district name column
    district_display = DISTRICT_BOUNDS[district]["display"].upper()
    if SHAPEFILE_DISTRICT_COL in gdf.columns:
        mask = gdf[SHAPEFILE_DISTRICT_COL].str.upper() == district_display
        if mask.sum() > 0:
            gdf = gdf[mask].reset_index(drop=True)

    logger.info("Loaded %d subdivisions for %s", len(gdf), district)
    return gdf


def list_subdivisions(district: str) -> list[dict]:
    """
    Return a lightweight list of {name, district} dicts for a district.
    Useful for populating UI dropdowns without loading full geometries.
    """
    gdf = load_subdivisions(district)
    return [
        {
            "name":     str(row[SHAPEFILE_SUBDIV_COL]),
            "district": str(row[SHAPEFILE_DISTRICT_COL]),
        }
        for _, row in gdf.iterrows()
    ]
