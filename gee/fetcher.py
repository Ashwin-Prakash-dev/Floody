"""
gee/fetcher.py
--------------
Fetches Sentinel-1 SAR image pairs from Google Earth Engine.

Public API
----------
    fetch_image_pair(district, event_date, baseline_date=None) -> ImagePair

Returns two local GeoTIFF paths (baseline + event) ready for the
analysis pipeline.  Images are cached by (district, date) so repeated
calls for the same parameters skip the GEE download.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from urllib.request import urlretrieve

import ee

from config.settings import (
    BASELINE_MIN_DAYS,
    BASELINE_WINDOW_DAYS,
    CACHE_DIR,
    DEM_COLLECTION,
    DISTRICT_BOUNDS,
    GCS_BUCKET,
    JRC_COLLECTION,
    JRC_OCCURRENCE_THRESHOLD,
    S1_COLLECTION,
    S1_MODE,
    S1_ORBIT,
    S1_POLARIZATION,
    S1_RESOLUTION,
)
from gee.auth import init_gee

logger = logging.getLogger(__name__)

# Max pixels GEE allows in getDownloadURL before it refuses.
# ~40 MP (2° × 2° at 10 m ≈ 20 MP for Idukki) usually fits.
_MAX_DOWNLOAD_PIXELS = 50_000_000


@dataclass
class ImagePair:
    district: str
    event_date: date
    baseline_date: date
    event_tif: Path
    baseline_tif: Path
    event_image_id: str
    baseline_image_id: str


# ── helpers ────────────────────────────────────────────────────────────────

def _cache_path(district: str, img_date: date, tag: str) -> Path:
    key = f"{district}_{img_date.isoformat()}_{tag}"
    return CACHE_DIR / f"{key}.tif"


def _bbox_to_geometry(bbox: list[float]) -> ee.Geometry:
    """[W, S, E, N] -> ee.Geometry.Rectangle."""
    return ee.Geometry.Rectangle(bbox)


def _s1_collection(geometry: ee.Geometry) -> ee.ImageCollection:
    """Return a filtered S1 collection clipped to geometry."""
    return (
        ee.ImageCollection(S1_COLLECTION)
        .filterBounds(geometry)
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", S1_POLARIZATION))
        .filter(ee.Filter.eq("instrumentMode", S1_MODE))
        .filter(ee.Filter.eq("orbitProperties_pass", S1_ORBIT))
        .select(S1_POLARIZATION)
    )


def _pick_best_image(
    collection: ee.ImageCollection,
    start: date,
    end: date,
    geometry: ee.Geometry,
) -> Optional[ee.Image]:
    """
    Return the image closest to `end` in [start, end] with the most
    valid pixels.  Returns None if the collection is empty.
    """
    filtered = collection.filterDate(start.isoformat(), (end + timedelta(days=1)).isoformat())
    size = filtered.size().getInfo()
    if size == 0:
        return None
    # mosaic by most-recent first (GEE mosaics stack last-on-top)
    return filtered.sort("system:time_start", False).first()


def _image_date(image: ee.Image) -> date:
    ts_ms = image.get("system:time_start").getInfo()
    return date.fromtimestamp(ts_ms / 1000)


def _download_tif(image: ee.Image, geometry: ee.Geometry, out_path: Path) -> None:
    if out_path.exists():
        logger.debug("Cache hit: %s", out_path)
        return

    import numpy as np
    import rasterio
    from rasterio.transform import from_bounds
    from affine import Affine

    logger.info("Downloading GeoTIFF via computePixels → %s", out_path.name)

    # Get bounds
    bounds = geometry.bounds().getInfo()["coordinates"][0]
    lons = [p[0] for p in bounds]
    lats = [p[1] for p in bounds]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)

    # Calculate dimensions at requested resolution
    # 1 degree ≈ 111320m
    import math
    cos_lat = math.cos(math.radians((north + south) / 2))
    width  = max(1, int((east - west)   * 111320 * cos_lat / S1_RESOLUTION))
    height = max(1, int((north - south) * 111320           / S1_RESOLUTION))

    # Cap to stay within limits
    max_dim = 4000
    if width > max_dim or height > max_dim:
        scale = max(width, height) / max_dim
        width  = int(width  / scale)
        height = int(height / scale)

    logger.info("Grid: %dx%d pixels", width, height)

    pixels = ee.data.computePixels({
        "expression": image,
        "fileFormat": "NUMPY_NDARRAY",
        "grid": {
            "dimensions": {"width": width, "height": height},
            "affineTransform": {
                "scaleX":     (east - west)   / width,
                "scaleY":    -(north - south) / height,
                "translateX": west,
                "translateY": north,
            },
            "crsCode": "EPSG:4326",
        },
    })

    # pixels is a numpy structured array — extract the band
    band_name = list(pixels.dtype.names)[0]
    data = pixels[band_name].astype(np.float32)

    transform = from_bounds(west, south, east, north, width, height)
    with rasterio.open(
        out_path, "w",
        driver="GTiff",
        height=height, width=width,
        count=1, dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=0,
    ) as dst:
        dst.write(data, 1)

    logger.info("Download complete: %s (%.1f MB)", out_path.name, out_path.stat().st_size / 1e6)


def _export_via_gcs(image: ee.Image, geometry: ee.Geometry, out_path: Path) -> None:
    """
    Export image to GCS then download.  Blocks until the task finishes.
    Requires GCS_BUCKET to be configured.
    """
    from google.cloud import storage  # type: ignore

    blob_name = out_path.stem
    task = ee.batch.Export.image.toCloudStorage(
        image=image,
        description=blob_name,
        bucket=GCS_BUCKET,
        fileNamePrefix=blob_name,
        scale=S1_RESOLUTION,
        region=geometry,
        fileFormat="GeoTIFF",
        crs="EPSG:4326",
        maxPixels=1e10,
    )
    task.start()
    logger.info("GCS export task started: %s. Waiting…", blob_name)

    import time
    while task.active():
        time.sleep(15)
        status = task.status()
        logger.debug("Task state: %s", status["state"])

    if task.status()["state"] != "COMPLETED":
        raise RuntimeError(f"GEE export task failed: {task.status()}")

    # Download from GCS
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(f"{blob_name}.tif")
    blob.download_to_filename(str(out_path))
    logger.info("Downloaded from GCS: %s", out_path.name)


# ── JRC + DEM masks ────────────────────────────────────────────────────────

def get_jrc_water_mask(geometry: ee.Geometry) -> ee.Image:
    """Return a binary mask: 1 = permanent water (to be excluded)."""
    jrc = ee.Image(JRC_COLLECTION).select("occurrence")
    return jrc.gte(JRC_OCCURRENCE_THRESHOLD).clip(geometry)


def get_slope_mask(geometry: ee.Geometry, max_slope: float) -> ee.Image:
    """Return a binary mask: 1 = slope too steep (to be excluded)."""
    dem = ee.Image(DEM_COLLECTION)
    slope = ee.Terrain.slope(dem)
    return slope.gte(max_slope).clip(geometry)


def download_ancillary_masks(district: str, geometry: ee.Geometry) -> dict[str, Path]:
    """Download JRC and slope mask GeoTIFFs for a district."""
    from config.settings import MAX_SLOPE_DEGREES

    paths = {}

    jrc_path = CACHE_DIR / f"{district}_jrc_mask.tif"
    if not jrc_path.exists():
        logger.info("Downloading JRC water mask for %s…", district)
        _download_tif(get_jrc_water_mask(geometry), geometry, jrc_path)
    paths["jrc"] = jrc_path

    slope_path = CACHE_DIR / f"{district}_slope_mask_{int(MAX_SLOPE_DEGREES)}deg.tif"
    if not slope_path.exists():
        logger.info("Downloading slope mask for %s…", district)
        _download_tif(get_slope_mask(geometry, MAX_SLOPE_DEGREES), geometry, slope_path)
    paths["slope"] = slope_path

    return paths


# ── public API ─────────────────────────────────────────────────────────────

def fetch_image_pair(
    district: str,
    event_date: date,
    baseline_date: Optional[date] = None,
) -> ImagePair:
    init_gee()

    if district not in DISTRICT_BOUNDS:
        raise ValueError(f"Unknown district '{district}'. Choose from {list(DISTRICT_BOUNDS)}")

    bbox = DISTRICT_BOUNDS[district]["bbox"]
    geometry = _bbox_to_geometry(bbox)
    s1 = _s1_collection(geometry)

    # ── Event composite ────────────────────────────────────────────────────
    # Use a 12-day window centred on event_date to catch at least one full pass
    event_start = event_date - timedelta(days=6)
    event_end   = event_date + timedelta(days=6)

    event_col = s1.filterDate(event_start.isoformat(), event_end.isoformat())
    if event_col.size().getInfo() == 0:
        raise ValueError(
            f"No Sentinel-1 images found around {event_date} for {district}."
        )
    event_img = event_col.median().clip(geometry)
    logger.info("Event composite: %s to %s (%d images)",
                event_start, event_end, event_col.size().getInfo())

    # ── Baseline composite ─────────────────────────────────────────────────
    if baseline_date is not None:
        bl_start = baseline_date - timedelta(days=6)
        bl_end   = baseline_date + timedelta(days=6)
    else:
        bl_end   = event_date - timedelta(days=BASELINE_MIN_DAYS)
        bl_start = bl_end - timedelta(days=BASELINE_WINDOW_DAYS)

    bl_col = s1.filterDate(bl_start.isoformat(), bl_end.isoformat())
    if bl_col.size().getInfo() == 0:
        raise ValueError(
            f"No baseline images found in [{bl_start}, {bl_end}] for {district}."
        )
    bl_img = bl_col.median().clip(geometry)
    logger.info("Baseline composite: %s to %s (%d images)",
                bl_start, bl_end, bl_col.size().getInfo())

    # Use the requested dates as cache keys (not actual image dates)
    actual_bl_date = baseline_date if baseline_date else (bl_end - timedelta(days=BASELINE_WINDOW_DAYS // 2))

    # ── Download ───────────────────────────────────────────────────────────
    event_tif    = _cache_path(district, event_date,    "event")
    baseline_tif = _cache_path(district, actual_bl_date, "baseline")

    _download_tif(event_img, geometry, event_tif)
    _download_tif(bl_img,    geometry, baseline_tif)

    return ImagePair(
        district=district,
        event_date=event_date,
        baseline_date=actual_bl_date,
        event_tif=event_tif,
        baseline_tif=baseline_tif,
        event_image_id=f"composite_{event_start}_{event_end}",
        baseline_image_id=f"composite_{bl_start}_{bl_end}",
    )