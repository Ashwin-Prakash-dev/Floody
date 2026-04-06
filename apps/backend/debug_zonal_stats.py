#!/usr/bin/env python3
"""
Debug script to diagnose zonal_stats zero-pixel issue.
Checks CRS alignment, raster bounds, and polygon-raster overlap.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.DEBUG, format="%(name)s | %(levelname)s | %(message)s")

from analysis.shapefile_loader import load_subdivisions
import rasterio
import geopandas as gpd

# Load a sample shapefile and check CRS
district = "wayanad"
print(f"\n{'='*70}")
print(f"DEBUG: Checking raster-shapefile alignment for {district}")
print(f"{'='*70}\n")

# Load subdivisions
subdivisions = load_subdivisions(district)
print(f"Subdivisions CRS: {subdivisions.crs}")
print(f"Subdivisions count: {len(subdivisions)}")
print(f"First subdivision bounds: {subdivisions.iloc[0].geometry.bounds}")
print(f"All subdivisions bounds: {subdivisions.total_bounds}")

# Try to open a sample flood mask if it exists
from config.settings import CACHE_DIR
mask_files = list(CACHE_DIR.glob(f"{district}_*_flood_mask.tif"))
if mask_files:
    mask_path = mask_files[-1]  # Latest mask
    print(f"\n✓ Found mask: {mask_path}")

    with rasterio.open(mask_path) as src:
        print(f"  Raster CRS: {src.crs}")
        print(f"  Raster bounds: {src.bounds}")
        print(f"  Raster shape: {src.shape}")
        print(f"  Raster transform: {src.transform}")

        # Check bounds overlap
        sub_bounds = subdivisions.total_bounds  # (minx, miny, maxx, maxy)
        raster_bounds = src.bounds  # (left, bottom, right, top)

        overlap_x = not (raster_bounds.right < sub_bounds[0] or raster_bounds.left > sub_bounds[2])
        overlap_y = not (raster_bounds.top < sub_bounds[1] or raster_bounds.bottom > sub_bounds[3])

        print(f"\n  Overlap X: {overlap_x}")
        print(f"  Overlap Y: {overlap_y}")
        print(f"  Total overlap: {overlap_x and overlap_y}")

        if not (overlap_x and overlap_y):
            print("  ⚠️  BOUNDS DO NOT OVERLAP!")
else:
    print(f"\n✗ No mask files found in {CACHE_DIR}")
    print("  Run a flood detection request first")

print(f"\n{'='*70}\n")
