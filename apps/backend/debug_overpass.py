#!/usr/bin/env python3
"""
Debug script to test Overpass API queries and print request/response details.
"""

import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s | %(levelname)-8s | %(message)s",
)

# Now test a single Overpass query
from analysis.vulnerability import _fetch_for_bbox, _bbox_str
from shapely.geometry import box

# Create a small test bbox (Wayanad area)
test_geom = box(75.7, 11.4, 76.4, 11.9)
bbox = _bbox_str(test_geom)

print(f"\n{'='*70}")
print(f"Testing Overpass API with bbox: {bbox}")
print(f"{'='*70}\n")

# Try fetching buildings
print("Fetching buildings...")
elements = _fetch_for_bbox(bbox, '["building"]')
print(f"Got {len(elements)} building elements\n")

# Try fetching schools
print("Fetching schools...")
elements = _fetch_for_bbox(bbox, '["amenity"~"school|college|university|kindergarten"]')
print(f"Got {len(elements)} school elements\n")

print("Debug test complete.")
