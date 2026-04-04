"""
Download Sentinel-1 SAR imagery for Idukki district, Kerala
using the Google Earth Engine (GEE) Python API.

Requirements:
    pip install earthengine-api geemap
    earthengine authenticate   # run once in terminal
"""

import ee
import os

# ── 1. Authenticate & Initialize ────────────────────────────────────────────
# First time: run `earthengine authenticate` in your terminal.
# After that, this line handles it automatically.
ee.Initialize(project='rotterdam-484003')   # replace with your GCP project ID


# ── 2. Define AOI — Idukki District, Kerala ─────────────────────────────────
# Approximate bounding box for Idukki district
# (covers the hilly/reservoir region including Idukki dam area)
idukki_bbox = ee.Geometry.Rectangle([76.7, 9.6, 77.4, 10.3])

# OR use the GAUL/FAO admin boundaries for a precise district polygon:
# idukki_aoi = (
#     ee.FeatureCollection("FAO/GAUL/2015/level2")
#     .filter(ee.Filter.And(
#         ee.Filter.eq("ADM1_NAME", "Kerala"),
#         ee.Filter.eq("ADM2_NAME", "Idukki")
#     ))
#     .geometry()
# )
# Uncomment the block above and replace idukki_bbox with idukki_aoi below
# if you want the exact district boundary instead of a rectangle.

aoi = idukki_bbox


# ── 3. Load & Filter Sentinel-1 GRD Collection ──────────────────────────────
START_DATE = "2024-06-01"
END_DATE   = "2024-09-30"    # Kerala monsoon window — adjust as needed

s1_collection = (
    ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterBounds(aoi)
    .filterDate(START_DATE, END_DATE)
    .filter(ee.Filter.eq("instrumentMode", "IW"))          # Interferometric Wide Swath
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))  # change to ASCENDING if needed
    .select(["VV", "VH"])
)

print("Number of images found:", s1_collection.size().getInfo())


# ── 4. Create a Median Composite ────────────────────────────────────────────
# Taking the median reduces speckle and handles missing data across passes.
# For flood detection, you may prefer a single date image — see Option B below.

# Option A: Median composite (recommended for general analysis)
sar_composite = s1_collection.median().clip(aoi)

# Option B: Single most-recent image
# latest_image = s1_collection.sort("system:time_start", False).first().clip(aoi)
# sar_composite = latest_image


# ── 5. Optional — Convert to dB scale ───────────────────────────────────────
# GEE stores S1 GRD values in linear scale. Convert to dB for interpretation.
def to_db(image):
    return image.log10().multiply(10)

sar_db = to_db(sar_composite)


# ── 6A. Export to Google Drive ───────────────────────────────────────────────
# This is the standard approach for large regions like Idukki.
# The file will appear in your Google Drive under the specified folder.

task = ee.batch.Export.image.toDrive(
    image=sar_db,
    description="Idukki_SAR_S1_Median_dB",
    folder="GEE_Exports",                  # folder in your Drive (created if absent)
    fileNamePrefix="idukki_sar_vv_vh_db",
    region=aoi,
    scale=10,                              # Sentinel-1 native resolution = 10m
    crs="EPSG:32643",                      # UTM Zone 43N — appropriate for Kerala
    maxPixels=1e13,
    fileFormat="GeoTIFF",
)

task.start()
print("Export task started. Task ID:", task.id)
print("Monitor at: https://code.earthengine.google.com/tasks")


# ── 6B. (Alternative) Download Directly as ZIP ──────────────────────────────
# Suitable for small AOIs only. For full Idukki district at 10m,
# use Drive export above to avoid size limits.

# import requests, zipfile, io
# url = sar_db.getDownloadURL({
#     "name": "idukki_sar",
#     "bands": ["VV", "VH"],
#     "region": aoi,
#     "scale": 30,            # coarser scale to stay within size limits
#     "crs": "EPSG:32643",
#     "format": "GeoTIFF",
# })
# print("Download URL:", url)
# r = requests.get(url)
# z = zipfile.ZipFile(io.BytesIO(r.content))
# z.extractall("./idukki_sar_output/")
# print("Downloaded and extracted to ./idukki_sar_output/")


# ── 7. Check Export Task Status ─────────────────────────────────────────────
import time

def monitor_task(task, poll_interval=30):
    """Poll the export task until it completes or fails."""
    while True:
        status = task.status()
        state  = status["state"]
        print(f"Task state: {state}")
        if state in ("COMPLETED", "FAILED", "CANCELLED"):
            if state == "FAILED":
                print("Error:", status.get("error_message"))
            break
        time.sleep(poll_interval)

# Uncomment to block and wait for completion:
# monitor_task(task)