"""
analysis/flood_detector.py
--------------------------
Core flood detection pipeline.

Pipeline
--------
1. load_and_align()   – read both GeoTIFFs, reproject to a common grid
2. to_db()            – linear power → dB
3. compute_difference()  – event_dB - baseline_dB
4. compute_threshold()   – Otsu or fixed dB threshold
5. build_flood_mask()    – binary flood raster, with JRC + slope masks applied
6. zonal_flood_stats()   – per-subdivision flood % using rasterstats
7. detect_floods()       – orchestrates everything; returns FloodResult

Public API
----------
    from analysis.flood_detector import detect_floods
    result = detect_floods(image_pair, subdivisions_gdf)
"""

from __future__ import annotations

import logging
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import calculate_default_transform, reproject
from rasterstats import zonal_stats
from skimage.filters import threshold_otsu

from config.settings import FLOOD_THRESHOLD_DB, MAX_SLOPE_DEGREES, OUTPUT_CRS

logger = logging.getLogger(__name__)


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class RasterData:
    """Holds a 2-D numpy array together with its affine transform and CRS."""
    data: np.ndarray        # shape (H, W), dtype float32; nodata → -9999.0
    transform: object       # affine.Affine
    crs: str
    nodata: float = -9999.0


@dataclass
class FloodResult:
    district: str
    event_date: object          # datetime.date
    baseline_date: object       # datetime.date
    threshold_db: float
    total_flooded_ha: float
    total_area_ha: float
    flood_pct_overall: float
    subdivisions: list[dict]    # per-subdivision records
    flood_mask_tif: Path        # path to the binary flood raster (for viz)


# ── Step 1: Load & align ───────────────────────────────────────────────────

def _read_raster(path: Path) -> RasterData:
    """Read a single-band GeoTIFF into a RasterData (float32, NaN for nodata)."""
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        nodata = src.nodata
        transform = src.transform
        crs = src.crs.to_string()
        logger.debug(
            "Read raster %s: shape=%s, transform=%s, crs=%s, nodata=%s",
            path.name, data.shape, transform, crs, nodata
        )

    if nodata is not None:
        data[data == nodata] = -9999.0

    # GEE sometimes outputs 0 for masked pixels in SAR exports
    data[data == 0] = -9999.0

    return RasterData(data=data, transform=transform, crs=crs)


def _reproject_to_match(source: RasterData, target: RasterData) -> RasterData:
    """Reproject source onto the grid of target."""
    if (
        source.crs == target.crs
        and source.data.shape == target.data.shape
        and source.transform == target.transform
    ):
        return source  # already aligned

    dst_data = np.empty(target.data.shape, dtype=np.float32)
    reproject(
        source=source.data,
        destination=dst_data,
        src_transform=source.transform,
        src_crs=source.crs,
        dst_transform=target.transform,
        dst_crs=target.crs,
        resampling=Resampling.bilinear,
        src_nodata=-9999.0,
        dst_nodata=-9999.0,
    )
    return RasterData(data=dst_data, transform=target.transform, crs=target.crs)


def load_and_align(event_tif: Path, baseline_tif: Path) -> tuple[RasterData, RasterData]:
    """Read both images and ensure they share the same grid."""
    event    = _read_raster(event_tif)
    baseline = _read_raster(baseline_tif)
    baseline = _reproject_to_match(baseline, event)
    logger.info(
        "Rasters aligned: shape=%s  crs=%s", event.data.shape, event.crs
    )
    return event, baseline


# ── Step 2: dB conversion ──────────────────────────────────────────────────

def to_db(raster: RasterData) -> RasterData:
    """
    Convert linear power (GEE S1 GRD default) to dB.
        dB = 10 * log10(linear)
    Zeros and negatives are masked.
    """
    data = raster.data.copy()
    invalid = (data <= 0) | (data == -9999.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        data = 10.0 * np.log10(np.where(invalid, -9999.0, data))
    data[invalid] = -9999.0
    return RasterData(data=data, transform=raster.transform, crs=raster.crs)


# ── Step 3: Difference image ───────────────────────────────────────────────

def compute_difference(event_db: RasterData, baseline_db: RasterData) -> RasterData:
    """
    event_dB - baseline_dB.
    A large negative value means backscatter dropped → likely flooding.
    """
    diff = event_db.data - baseline_db.data
    return RasterData(data=diff, transform=event_db.transform, crs=event_db.crs)


# ── Step 4: Threshold ──────────────────────────────────────────────────────

def compute_threshold(diff: RasterData, fixed_threshold_db: Optional[float] = None) -> float:
    """
    Determine the dB threshold below which a pixel is flooded.

    If fixed_threshold_db is given, use it directly.
    Otherwise apply Otsu's method to the histogram of valid difference pixels.
    Otsu finds the value that maximises inter-class variance (water vs land).
    """
    if fixed_threshold_db is not None:
        logger.info("Using fixed threshold: %.2f dB", fixed_threshold_db)
        return float(fixed_threshold_db)

    valid = diff.data[diff.data != -9999.0]
    if valid.size == 0:
        raise ValueError("Difference raster has no valid pixels.")

    # Otsu on the raw pixel distribution
    # Clip extreme outliers first (±3σ) so they don't skew the histogram
    mu, sigma = valid.mean(), valid.std()
    clipped = valid[(valid > mu - 3 * sigma) & (valid < mu + 3 * sigma)]

    thresh = float(threshold_otsu(clipped))
    # Sanity clamp: don't let Otsu push threshold above -1 dB or below -10 dB
    thresh = max(-10.0, min(-1.0, thresh))
    logger.info("Otsu threshold: %.3f dB  (from %d valid pixels)", thresh, valid.size)
    return thresh


# ── Step 5: Flood mask ─────────────────────────────────────────────────────

def _load_ancillary_mask(tif_path: Optional[Path], shape: tuple, transform, crs: str) -> np.ndarray:
    if tif_path is None or not tif_path.exists():
        return np.zeros(shape, dtype=bool)
    import rasterio
    with rasterio.open(tif_path) as src:
        data = src.read(1).astype(np.float32)
        file_transform = src.transform
        file_crs = src.crs.to_string()
    nodata = getattr(src, 'nodata', -9999.0)
    non_zero = (data != 0) & (data != nodata)
    raw = RasterData(data=non_zero.astype(np.float32), transform=file_transform, crs=file_crs)
    target = RasterData(data=np.zeros(shape, dtype=np.float32), transform=transform, crs=crs)
    matched = _reproject_to_match(raw, target)
    return matched.data > 0.5

def build_flood_mask(
    diff: RasterData,
    threshold_db: float,
    jrc_mask_tif: Optional[Path] = None,
    slope_mask_tif: Optional[Path] = None,
) -> RasterData:
    """
    Binary flood raster: 1 = flooded, 0 = not flooded, NaN = nodata.

    Exclusions applied:
      - pixels above threshold (not a backscatter drop)
      - NaN pixels in the difference image
      - permanent water (JRC mask)
      - steep terrain (slope mask)
    """
    flooded = (diff.data < threshold_db) & (diff.data != -9999.0)

    # Remove permanent water
    jrc = _load_ancillary_mask(jrc_mask_tif, diff.data.shape, diff.transform, diff.crs)
    flooded &= ~jrc

    # Remove steep terrain
    slope = _load_ancillary_mask(slope_mask_tif, diff.data.shape, diff.transform, diff.crs)
    flooded &= ~slope

    mask_data = np.where(diff.data == -9999.0, -9999.0, flooded.astype(np.float32))
    n_flooded = int(flooded.sum())
    logger.info(
        "Flood mask built: %d flooded pixels (threshold=%.2f dB)", n_flooded, threshold_db
    )
    return RasterData(data=mask_data, transform=diff.transform, crs=diff.crs)


def save_raster(raster: RasterData, out_path: Path) -> None:
    """Write a RasterData to a GeoTIFF (float32, LZW compressed)."""
    H, W = raster.data.shape
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=H,
        width=W,
        count=1,
        dtype="float32",
        crs=raster.crs,
        transform=raster.transform,
        nodata=raster.nodata,
        compress="lzw",
    ) as dst:
        dst.write(raster.data, 1)


# ── Step 6: Zonal statistics ───────────────────────────────────────────────

def _pixel_area_ha(transform) -> float:
    """
    Approximate area (hectares) of one pixel, assuming geographic CRS.
    Uses the mean latitude of the image to correct for longitude compression.
    """
    # affine: (x_res, 0, x_min, 0, -y_res, y_max)
    lon_res = abs(transform.a)   # degrees per pixel in x
    lat_res = abs(transform.e)   # degrees per pixel in y
    # 1° latitude ≈ 111 320 m; 1° longitude ≈ 111 320 * cos(lat) m
    # For the Kerala districts (≈10°N) cos(10°) ≈ 0.985
    import math
    cos_lat = math.cos(math.radians(10.0))
    m_per_px_x = lon_res * 111_320 * cos_lat
    m_per_px_y = lat_res * 111_320
    return (m_per_px_x * m_per_px_y) / 10_000   # m² → ha


def zonal_flood_stats(
    flood_mask: RasterData,
    subdivisions: gpd.GeoDataFrame,
    subdiv_col: str,
    district_col: str,
) -> list[dict]:
    """
    Compute flooded-area statistics per subdivision polygon.

    Returns a list of dicts, one per subdivision:
        {
          "subdivision": str,
          "district": str,
          "total_pixels": int,
          "flooded_pixels": int,
          "flooded_ha": float,
          "total_ha": float,
          "flood_pct": float,          # 0–100
          "geometry": dict,            # GeoJSON-ready
        }
    """
    # Reproject subdivisions to raster CRS if needed
    raster_crs = flood_mask.crs
    subdiv_crs_before = subdivisions.crs.to_string()
    logger.info("Before reprojection: subdiv_crs=%s, raster_crs=%s", subdiv_crs_before, raster_crs)
    logger.info("Subdivisions bounds: %s", subdivisions.total_bounds)
    logger.info("Raster transform: %s, shape: %s", flood_mask.transform, flood_mask.data.shape)

    if subdiv_crs_before != raster_crs:
        logger.info("Reprojecting subdivisions: %s → %s", subdiv_crs_before, raster_crs)
        subdivisions = subdivisions.to_crs(raster_crs)
        logger.info("After reprojection bounds: %s", subdivisions.total_bounds)
    else:
        logger.info("Subdivisions CRS matches raster: %s", raster_crs)

    px_ha = _pixel_area_ha(flood_mask.transform)

    logger.info("Zonal stats: using in-memory raster (bypassing GDAL temp file)")
    logger.info("Raster shape=%s, crs=%s", flood_mask.data.shape, flood_mask.crs)
    logger.info("Subdivisions count=%d, bounds=%s", len(subdivisions), subdivisions.total_bounds)

    # Use rasterstats with in-memory data instead of temp file (avoids GDAL compatibility issues)
    stats = zonal_stats(
        subdivisions,
        flood_mask.data,
        affine=flood_mask.transform,
        crs=flood_mask.crs,
        stats=["count", "sum"],
        nodata=-9999.0,
        all_touched=True,  # Include pixels that touch polygon boundary
    )
    logger.info("Zonal stats returned %d results", len(stats))

    records = []
    zero_count = 0
    for row, stat in zip(subdivisions.itertuples(), stats):
        total_px   = int(stat.get("count") or 0)
        flooded_px = int(stat.get("sum") or 0)
        flooded_ha = flooded_px * px_ha
        total_ha   = total_px * px_ha
        pct        = (flooded_px / total_px * 100) if total_px > 0 else 0.0

        subdiv_name  = getattr(row, subdiv_col,  "Unknown")
        district_name = getattr(row, district_col, "Unknown")

        if total_px == 0:
            zero_count += 1
            logger.warning(
                "  %-30s  ⚠️  ZERO PIXELS (raster not overlapping?) crs=%s bound=%s",
                subdiv_name, subdivisions.crs, row.geometry.bounds
            )

        records.append(
            {
                "subdivision":    str(subdiv_name),
                "district":       str(district_name),
                "total_pixels":   total_px,
                "flooded_pixels": flooded_px,
                "flooded_ha":     round(flooded_ha, 2),
                "total_ha":       round(total_ha, 2),
                "flood_pct":      round(pct, 2),
                "geometry":       row.geometry.__geo_interface__,
            }
        )
        logger.debug(
            "  %-30s  flooded: %5.1f ha  (%.1f%%)", subdiv_name, flooded_ha, pct
        )

    if zero_count > 0:
        logger.warning("⚠️  %d/%d subdivisions have zero pixels (CRS mismatch or no raster overlap)",
                      zero_count, len(records))

    records.sort(key=lambda r: r["flood_pct"], reverse=True)
    return records


# ── Orchestrator ───────────────────────────────────────────────────────────

def detect_floods(
    image_pair,                     # gee.fetcher.ImagePair
    subdivisions_gdf: gpd.GeoDataFrame,
    subdiv_col: str,
    district_col: str,
    jrc_mask_tif: Optional[Path] = None,
    slope_mask_tif: Optional[Path] = None,
    out_dir: Optional[Path] = None,
) -> FloodResult:
    """
    End-to-end flood detection for one district event.

    Parameters
    ----------
    image_pair       : ImagePair from gee.fetcher.fetch_image_pair()
    subdivisions_gdf : GeoDataFrame of subdivision polygons (clipped to district)
    subdiv_col       : Column name for subdivision name in gdf
    district_col     : Column name for district name in gdf
    jrc_mask_tif     : Path to JRC permanent-water mask GeoTIFF (optional)
    slope_mask_tif   : Path to slope mask GeoTIFF (optional)
    out_dir          : Directory to write output GeoTIFFs (default: CACHE_DIR)

    Returns
    -------
    FloodResult
    """
    from config.settings import CACHE_DIR, SHAPEFILE_DISTRICT_COL, SHAPEFILE_SUBDIV_COL

    if out_dir is None:
        out_dir = CACHE_DIR

    logger.info("=== Flood detection: %s | event=%s | baseline=%s ===",
                image_pair.district, image_pair.event_date, image_pair.baseline_date)

    # 1. Load + align
    event_raw, baseline_raw = load_and_align(image_pair.event_tif, image_pair.baseline_tif)

    # 2. dB conversion
    event_db    = to_db(event_raw)
    baseline_db = to_db(baseline_raw)

    # 3. Difference
    diff = compute_difference(event_db, baseline_db)

    # 4. Threshold
    thresh = compute_threshold(diff, FLOOD_THRESHOLD_DB)

    # 5. Flood mask
    flood_mask = build_flood_mask(diff, thresh, jrc_mask_tif, slope_mask_tif)

    # Save flood mask raster
    mask_path = out_dir / f"{image_pair.district}_{image_pair.event_date}_flood_mask.tif"
    save_raster(flood_mask, mask_path)
    logger.info("Flood mask saved: %s", mask_path)

    # 6. Zonal stats
    px_ha = _pixel_area_ha(flood_mask.transform)
    valid_px   = int(np.sum(~np.isnan(flood_mask.data)))
    flooded_px = int(np.nansum(flood_mask.data))
    total_ha   = valid_px   * px_ha
    flooded_ha = flooded_px * px_ha
    overall_pct = (flooded_px / valid_px * 100) if valid_px > 0 else 0.0

    subdivision_stats = zonal_flood_stats(
        flood_mask, subdivisions_gdf, subdiv_col, district_col
    )

    logger.info(
        "District total: %.1f ha flooded / %.1f ha total (%.2f%%)",
        flooded_ha, total_ha, overall_pct,
    )

    return FloodResult(
        district=image_pair.district,
        event_date=image_pair.event_date,
        baseline_date=image_pair.baseline_date,
        threshold_db=thresh,
        total_flooded_ha=round(flooded_ha, 2),
        total_area_ha=round(total_ha, 2),
        flood_pct_overall=round(overall_pct, 2),
        subdivisions=subdivision_stats,
        flood_mask_tif=mask_path,
    )
