"""
gee/auth.py
-----------
Handles Google Earth Engine authentication.

Two modes:
  1. Service account (production): provide a JSON key file path via
     GEE_SERVICE_ACCOUNT_KEY env var or config/settings.py.
  2. Interactive / Application Default Credentials (local dev):
     run `earthengine authenticate` once, then set GEE_USE_ADC=true.

Usage
-----
    from gee.auth import init_gee
    init_gee()          # call once at startup
"""

import logging
import os
from pathlib import Path

import ee

logger = logging.getLogger(__name__)

_initialised = False


def init_gee() -> None:
    """Authenticate and initialise the GEE Python client (idempotent)."""
    global _initialised
    if _initialised:
        return

    use_adc = os.getenv("GEE_USE_ADC", "false").lower() in ("1", "true", "yes")

    if use_adc:
        # Application Default Credentials — works after `earthengine authenticate`
        logger.info("GEE: using Application Default Credentials")
        try:
            project = os.getenv("GEE_PROJECT_ID")
            if project:
                ee.Initialize(project=project)
            else:
                ee.Initialize()
            _initialised = True
            logger.info("GEE initialised via ADC")
            return
        except Exception as exc:
            logger.error("GEE ADC init failed: %s", exc)
            raise

    # Service-account path: env var > config default
    key_path = os.getenv("GEE_SERVICE_ACCOUNT_KEY")
    if not key_path:
        from config.settings import GEE_SERVICE_ACCOUNT_KEY, GEE_PROJECT_ID
        key_path = GEE_SERVICE_ACCOUNT_KEY
        project_id = GEE_PROJECT_ID
    else:
        project_id = os.getenv("GEE_PROJECT_ID", "")

    key_file = Path(key_path)
    if not key_file.exists():
        raise FileNotFoundError(
            f"GEE service account key not found at '{key_file}'. "
            "Either place the key there, set GEE_SERVICE_ACCOUNT_KEY env var, "
            "or set GEE_USE_ADC=true for interactive auth."
        )

    credentials = ee.ServiceAccountCredentials(
        email=None,          # auto-read from the JSON
        key_file=str(key_file),
    )
    ee.Initialize(credentials=credentials, project=project_id)
    _initialised = True
    logger.info("GEE initialised via service account: %s", key_file)
