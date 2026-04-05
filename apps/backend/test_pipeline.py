"""
test_pipeline.py
----------------
End-to-end tests for the flood detection backend.

Test 1 — Real boundary validation
  Verifies that downloaded GeoJSON files load and clip correctly per district.
  Skips gracefully if download_boundaries.py hasn't been run yet.

Test 2 — Synthetic SAR pipeline
  Generates two synthetic SAR GeoTIFFs where a known rectangular region has a
  -5 dB backscatter drop (simulated flood), runs the full analysis pipeline
  against real village boundaries (or synthetic grid as fallback).
  No GEE auth required.

Run from the project root:
    python test_pipeline.py
"""

import logging
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s  %(message)s")
logger = logging.getLogger("test_pipeline")


# ── Synthetic raster helpers ───────────────────────────────────────────────

def _write_synthetic_sar(path: Path, data: np.ndarray, bbox: list) -> None:
    H, W = data.shape
    transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], W, H)
    with rasterio.open(
        path, "w", driver="GTiff",
        height=H, width=W, count=1,
        dtype="float32", crs="EPSG:4326",
        transform=transform, nodata=None,
    ) as dst:
        dst.write(data, 1)


def make_synthetic_pair(tmp_dir: Path, bbox: list, flood_fraction: float = 0.25):
    """
    Baseline: Gaussian noise ~0.15 linear power (typical land SAR backscatter).
    Event:    same, but top-left patch multiplied by 0.35 → ≈ -4.6 dB drop.
    """
    H, W = 200, 200
    rng = np.random.default_rng(42)
    baseline = np.clip(rng.normal(0.15, 0.02, (H, W)).astype(np.float32), 0.01, None)
    event = baseline.copy()
    flood_H = int(H * flood_fraction)
    flood_W = int(W * flood_fraction)
    event[:flood_H, :flood_W] *= 0.35

    baseline_path = tmp_dir / "baseline.tif"
    event_path    = tmp_dir / "event.tif"
    _write_synthetic_sar(baseline_path, baseline, bbox)
    _write_synthetic_sar(event_path,    event,    bbox)
    logger.info("Synthetic rasters written: baseline.tif, event.tif")
    return baseline_path, event_path, flood_H, flood_W, H, W


# ── Test 1: Real boundary validation ──────────────────────────────────────

def test_real_boundaries() -> None:
    from config.settings import SHAPEFILE_DIR
    geojson = SHAPEFILE_DIR / "kerala_subdivisions.geojson"
    if not geojson.exists():
        logger.warning("Skipping real boundary test — run download_boundaries.py first.")
        return

    from analysis.shapefile_loader import list_subdivisions, load_subdivisions

    logger.info("=== Test 1: Real boundary validation ===")
    for district, min_count in [("idukki", 60), ("wayanad", 40), ("ernakulam", 100)]:
        gdf   = load_subdivisions(district)
        names = list_subdivisions(district)
        assert len(gdf) >= min_count, \
            f"{district}: only {len(gdf)} features (expected >= {min_count})"
        assert len(names) == len(gdf)
        logger.info("  %-12s  %d villages  e.g. '%s'",
                    district, len(gdf), names[0]["name"])
    logger.info("PASS: all district boundaries loaded correctly.\n")


# ── Test 2: Synthetic SAR pipeline ────────────────────────────────────────

def test_synthetic_pipeline() -> None:
    from analysis.flood_detector import (
        build_flood_mask, compute_difference, compute_threshold,
        load_and_align, to_db, zonal_flood_stats,
    )
    from analysis.shapefile_loader import load_subdivisions
    from config.settings import DISTRICT_BOUNDS, SHAPEFILE_DISTRICT_COL, SHAPEFILE_SUBDIV_COL

    district = "wayanad"
    bbox = DISTRICT_BOUNDS[district]["bbox"]
    logger.info("=== Test 2: Synthetic SAR pipeline ===")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # 1. Synthetic SAR pair
        logger.info("--- Step 1: Generate synthetic SAR data ---")
        baseline_tif, event_tif, flood_H, flood_W, H, W = make_synthetic_pair(
            tmp_dir, bbox, flood_fraction=0.25
        )
        true_flood_px = flood_H * flood_W
        logger.info("True flooded pixels: %d / %d (%.1f%%)",
                    true_flood_px, H * W, true_flood_px / (H * W) * 100)

        # 2. Load & align
        logger.info("\n--- Step 2: Load & align ---")
        event_raw, baseline_raw = load_and_align(event_tif, baseline_tif)

        # 3. dB conversion
        logger.info("\n--- Step 3: dB conversion ---")
        event_db    = to_db(event_raw)
        baseline_db = to_db(baseline_raw)
        logger.info("Event dB:    mean=%.2f  min=%.2f  max=%.2f",
                    np.nanmean(event_db.data), np.nanmin(event_db.data), np.nanmax(event_db.data))
        logger.info("Baseline dB: mean=%.2f  min=%.2f  max=%.2f",
                    np.nanmean(baseline_db.data), np.nanmin(baseline_db.data), np.nanmax(baseline_db.data))

        # 4. Difference image
        logger.info("\n--- Step 4: Difference image ---")
        diff = compute_difference(event_db, baseline_db)
        logger.info("Flooded patch mean diff: %.2f dB  |  Land mean diff: %.2f dB",
                    np.nanmean(diff.data[:flood_H, :flood_W]),
                    np.nanmean(diff.data[flood_H:, :]))

        # 5. Otsu threshold
        logger.info("\n--- Step 5: Threshold (Otsu) ---")
        thresh = compute_threshold(diff, fixed_threshold_db=None)
        logger.info("Otsu threshold: %.3f dB", thresh)

        # 6. Flood mask
        logger.info("\n--- Step 6: Build flood mask ---")
        flood_mask = build_flood_mask(diff, thresh)
        detected_px = int(np.nansum(flood_mask.data))
        total_valid = int(np.sum(~np.isnan(flood_mask.data)))
        logger.info("Detected: %d / %d pixels flooded (%.1f%%)",
                    detected_px, total_valid, detected_px / total_valid * 100)

        quadrant_detected = int(np.nansum(flood_mask.data[:flood_H, :flood_W]))
        recall = quadrant_detected / true_flood_px
        logger.info("Recall in true flood zone: %.1f%%  (%d / %d px)",
                    recall * 100, quadrant_detected, true_flood_px)
        assert recall > 0.80, f"Detection recall too low: {recall:.2f}"
        logger.info("PASS: flood recall > 80%%")

        # 7. Zonal statistics
        logger.info("\n--- Step 7: Zonal statistics ---")
        gdf = load_subdivisions(district)
        using_real = "Cell" not in str(gdf.iloc[0][SHAPEFILE_SUBDIV_COL])
        logger.info("Using %s (%d subdivisions)",
                    "real village boundaries" if using_real else "synthetic grid",
                    len(gdf))

        records = zonal_flood_stats(
            flood_mask, gdf,
            subdiv_col=SHAPEFILE_SUBDIV_COL,
            district_col=SHAPEFILE_DISTRICT_COL,
        )

        logger.info("\n%-30s  %8s  %8s  %6s", "Subdivision", "Flood ha", "Total ha", "Flood%")
        logger.info("-" * 58)
        for r in records[:10]:
            logger.info("%-30s  %8.2f  %8.2f  %5.1f%%",
                        r["subdivision"], r["flooded_ha"], r["total_ha"], r["flood_pct"])
        if len(records) > 10:
            logger.info("  ... and %d more subdivisions", len(records) - 10)

        assert records[0]["flood_pct"] > 0, "Top subdivision should have flooding"
        logger.info("\nPASS: zonal stats returned %d subdivisions.", len(records))

        # 8. API import
        logger.info("\n--- Step 8: API import check ---")
        from api.app import app as fastapi_app
        assert fastapi_app is not None
        logger.info("PASS: FastAPI app imported cleanly.")

    logger.info("\n=== All tests passed ===")


def main() -> None:
    test_real_boundaries()
    test_synthetic_pipeline()


if __name__ == "__main__":
    main()
