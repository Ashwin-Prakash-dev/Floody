"""
api/app.py
----------
FastAPI application for the Kerala Flood Detection backend.

Endpoints
---------
GET  /health                    – liveness probe
GET  /districts                 – list supported districts with metadata
POST /flood-detection           – main analysis endpoint
GET  /flood-mask/{job_id}       – download the binary flood mask GeoTIFF
GET  /jobs/{job_id}             – check job status (for async polling)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from config.settings import CORS_ORIGINS, DISTRICT_BOUNDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Kerala SAR Flood Detection API",
    description=(
        "Sentinel-1 SAR-based flood detection for Idukki, Wayanad, and Ernakulam. "
        "Fetches image pairs from Google Earth Engine, runs threshold-based flood "
        "detection, and returns per-subdivision flood statistics."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── In-memory job store (replace with Redis/DB in production) ──────────────

class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


_jobs: dict[str, dict] = {}


# ── Pydantic models ────────────────────────────────────────────────────────

class FloodRequest(BaseModel):
    district: str
    event_date: date
    baseline_date: Optional[date] = None

    @field_validator("district")
    @classmethod
    def validate_district(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in DISTRICT_BOUNDS:
            raise ValueError(
                f"Unknown district '{v}'. Supported: {list(DISTRICT_BOUNDS.keys())}"
            )
        return v

    @field_validator("baseline_date")
    @classmethod
    def baseline_before_event(cls, v: Optional[date], info) -> Optional[date]:
        if v is not None:
            event = info.data.get("event_date")
            if event and v >= event:
                raise ValueError("baseline_date must be before event_date.")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "district": "wayanad",
                "event_date": "2019-08-10",
                "baseline_date": "2019-07-15",
            }
        }
    }


class SubdivisionResult(BaseModel):
    subdivision:       str
    district:          str
    flooded_ha:        float
    total_ha:          float
    flood_pct:         float
    building_density:  float = 0.0
    schools_count:     int   = 0
    hospitals_count:   int   = 0
    road_density:      float = 0.0
    severity_score:    float = 0.0
    severity_label:    str   = "LOW"
    severity_color:    str   = "#00c8ff"
    geometry:          dict             # GeoJSON geometry


class FloodResponse(BaseModel):
    job_id: str
    status: JobStatus
    district: str
    event_date: Optional[date]
    baseline_date: Optional[date]
    threshold_db: Optional[float]
    total_flooded_ha: Optional[float]
    total_area_ha: Optional[float]
    flood_pct_overall: Optional[float]
    subdivisions: list[SubdivisionResult]
    flood_mask_url: Optional[str]
    error: Optional[str]


# ── Background task ────────────────────────────────────────────────────────

def _run_flood_analysis(job_id: str, request: FloodRequest) -> None:
    """Executed in a background thread by FastAPI BackgroundTasks."""
    _jobs[job_id]["status"] = JobStatus.RUNNING

    try:
        from analysis.flood_detector import detect_floods
        from analysis.shapefile_loader import load_subdivisions
        from config.settings import SHAPEFILE_DISTRICT_COL, SHAPEFILE_SUBDIV_COL
        from gee.fetcher import download_ancillary_masks, fetch_image_pair

        # 1. Fetch SAR image pair from GEE
        logger.info("[%s] Fetching image pair from GEE…", job_id)
        pair = fetch_image_pair(
            district=request.district,
            event_date=request.event_date,
            baseline_date=request.baseline_date,
        )

        # 2. Download ancillary masks (JRC + slope)
        from gee.fetcher import _bbox_to_geometry
        import ee
        geometry = _bbox_to_geometry(DISTRICT_BOUNDS[request.district]["bbox"])
        masks = download_ancillary_masks(request.district, geometry)

        # 3. Load subdivision boundaries
        logger.info("[%s] Loading subdivision boundaries…", job_id)
        subdivisions_gdf = load_subdivisions(request.district)

        # 4. Run flood detection
        logger.info("[%s] Running flood detection…", job_id)
        result = detect_floods(
            image_pair=pair,
            subdivisions_gdf=subdivisions_gdf,
            subdiv_col=SHAPEFILE_SUBDIV_COL,
            district_col=SHAPEFILE_DISTRICT_COL,
            jrc_mask_tif=masks.get("jrc"),
            slope_mask_tif=masks.get("slope"),
        )

        _jobs[job_id].update(
            {
                "status":             JobStatus.COMPLETED,
                "event_date":         result.event_date,
                "baseline_date":      result.baseline_date,
                "threshold_db":       result.threshold_db,
                "total_flooded_ha":   result.total_flooded_ha,
                "total_area_ha":      result.total_area_ha,
                "flood_pct_overall":  result.flood_pct_overall,
                "subdivisions":       severity_dicts,
                "flood_mask_tif":     result.flood_mask_tif,
            }
        )
        logger.info("[%s] Analysis complete. Flooded: %.1f ha (%.2f%%)",
                    job_id, result.total_flooded_ha, result.flood_pct_overall)

    except Exception as exc:
        logger.exception("[%s] Analysis failed: %s", job_id, exc)
        _jobs[job_id]["status"] = JobStatus.FAILED
        _jobs[job_id]["error"]  = str(exc)
    
        # 5. Fetch vulnerability factors from OSM
    logger.info("[%s] Fetching OSM vulnerability factors…", job_id)
    from analysis.vulnerability import fetch_vulnerability_factors
    from analysis.severity_model import SeverityModel
    from config.settings import SHAPEFILE_SUBDIV_COL

    vuln_df = fetch_vulnerability_factors(
        subdivisions_gdf,
        subdiv_col=SHAPEFILE_SUBDIV_COL,
    )

    # 6. Run K-Means severity clustering
    logger.info("[%s] Running severity clustering…", job_id)
    model = SeverityModel(n_clusters=3)
    severity_results = model.fit_predict(result.subdivisions, vuln_df)

    # Convert severity results to dicts for the job store
    severity_dicts = [
        {
            "subdivision":      r.subdivision,
            "district":         r.district,
            "flooded_ha":       r.flooded_ha,
            "total_ha":         r.total_ha,
            "flood_pct":        r.flood_pct,
            "building_density": r.building_density,
            "schools_count":    r.schools_count,
            "hospitals_count":  r.hospitals_count,
            "road_density":     r.road_density,
            "severity_score":   r.severity_score,
            "severity_label":   r.severity_label,
            "severity_color":   r.severity_color,
            "geometry":         r.geometry,
        }
        for r in severity_results
    ]


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Utility"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/districts", tags=["Utility"])
def list_districts() -> dict:
    """Return supported districts with bounding boxes."""
    return {
        k: {"display": v["display"], "bbox": v["bbox"]}
        for k, v in DISTRICT_BOUNDS.items()
    }


@app.get("/subdivisions/{district}", tags=["Utility"])
def list_subdivisions(district: str) -> dict:
    """
    Return all subdivision (village) names for a district.
    Useful for populating frontend dropdowns.
    """
    district = district.lower().strip()
    if district not in DISTRICT_BOUNDS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown district '{district}'. Supported: {list(DISTRICT_BOUNDS.keys())}",
        )
    from analysis.shapefile_loader import list_subdivisions as _list
    subdivisions = _list(district)
    return {"district": district, "count": len(subdivisions), "subdivisions": subdivisions}


@app.post("/flood-detection", response_model=FloodResponse, tags=["Analysis"])
def start_flood_detection(
    request: FloodRequest,
    background_tasks: BackgroundTasks,
) -> FloodResponse:
    """
    Kick off flood detection for a district + date pair.

    The job runs in the background.  Poll GET /jobs/{job_id} until
    status == 'completed', then collect results from that same endpoint.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status":             JobStatus.PENDING,
        "district":           request.district,
        "event_date":         request.event_date,
        "baseline_date":      request.baseline_date,
        "threshold_db":       None,
        "total_flooded_ha":   None,
        "total_area_ha":      None,
        "flood_pct_overall":  None,
        "subdivisions":       [],
        "flood_mask_tif":     None,
        "error":              None,
    }
    background_tasks.add_task(_run_flood_analysis, job_id, request)
    logger.info("Job %s started: district=%s event=%s", job_id, request.district, request.event_date)
    return _job_to_response(job_id)


@app.get("/jobs/{job_id}", response_model=FloodResponse, tags=["Analysis"])
def get_job(job_id: str) -> FloodResponse:
    """Poll this endpoint to check job status and retrieve results."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return _job_to_response(job_id)


@app.get("/flood-mask/{job_id}", tags=["Analysis"])
def download_flood_mask(job_id: str) -> FileResponse:
    """Download the binary flood mask GeoTIFF for a completed job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = _jobs[job_id]
    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not yet completed.")
    tif_path: Optional[Path] = job.get("flood_mask_tif")
    if tif_path is None or not tif_path.exists():
        raise HTTPException(status_code=404, detail="Flood mask file not found.")
    return FileResponse(
        path=str(tif_path),
        media_type="image/tiff",
        filename=tif_path.name,
    )


# ── Helper ─────────────────────────────────────────────────────────────────

def _job_to_response(job_id: str) -> FloodResponse:
    j = _jobs[job_id]
    tif: Optional[Path] = j.get("flood_mask_tif")
    mask_url = f"/flood-mask/{job_id}" if tif and tif.exists() else None

    subdivisions = [
        SubdivisionResult(
            subdivision=s["subdivision"],
            district=s["district"],
            flooded_ha=s["flooded_ha"],
            total_ha=s["total_ha"],
            flood_pct=s["flood_pct"],
            geometry=s["geometry"],
        )
        for s in j.get("subdivisions", [])
    ]

    return FloodResponse(
        job_id=job_id,
        status=j["status"],
        district=j["district"],
        event_date=j.get("event_date"),
        baseline_date=j.get("baseline_date"),
        threshold_db=j.get("threshold_db"),
        total_flooded_ha=j.get("total_flooded_ha"),
        total_area_ha=j.get("total_area_ha"),
        flood_pct_overall=j.get("flood_pct_overall"),
        subdivisions=subdivisions,
        flood_mask_url=mask_url,
        error=j.get("error"),
    )
