import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
SHAPEFILE_DIR = DATA_DIR / 'shapefiles'
CACHE_DIR = DATA_DIR / 'cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

GEE_SERVICE_ACCOUNT_KEY = os.getenv('GEE_SERVICE_ACCOUNT_KEY', 'gee-service-account.json')
GEE_PROJECT_ID = os.getenv('GEE_PROJECT_ID', 'rotterdam-484003')
GCS_BUCKET = os.getenv('GCS_BUCKET', 'your-gcs-bucket')

DISTRICT_BOUNDS = {
    'idukki': {'bbox': [76.6, 9.6, 77.4, 10.4], 'display': 'Idukki'},
    'wayanad': {'bbox': [75.7, 11.4, 76.4, 11.9], 'display': 'Wayanad'},
    'ernakulam': {'bbox': [76.1, 9.8, 76.8, 10.3], 'display': 'Ernakulam'},
}

S1_COLLECTION = 'COPERNICUS/S1_GRD'
S1_POLARIZATION = 'VV'
S1_MODE = 'IW'
S1_ORBIT = 'DESCENDING'
S1_RESOLUTION = 50

BASELINE_WINDOW_DAYS = int(os.getenv('BASELINE_WINDOW_DAYS', '30'))
BASELINE_MIN_DAYS = int(os.getenv('BASELINE_MIN_DAYS', '6'))

FLOOD_THRESHOLD_DB = float(os.getenv('FLOOD_THRESHOLD_DB', '-3.0'))
MAX_SLOPE_DEGREES = float(os.getenv('MAX_SLOPE_DEGREES', '30.0'))
DEM_COLLECTION = os.getenv('DEM_COLLECTION', 'USGS/SRTMGL1_003')
JRC_COLLECTION = os.getenv('JRC_COLLECTION', 'JRC/GSW1_4/GlobalSurfaceWater')
JRC_OCCURRENCE_THRESHOLD = int(os.getenv('JRC_OCCURRENCE_THRESHOLD', '80'))

SHAPEFILE_DISTRICT_COL = 'DISTRICT'
SHAPEFILE_SUBDIV_COL = 'NAME'
SHAPEFILE_AREA_HA_COL = None

OUTPUT_CRS = os.getenv('OUTPUT_CRS', 'EPSG:4326')

API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8000'))
API_WORKERS = int(os.getenv('API_WORKERS', '1'))
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',') if os.getenv('CORS_ORIGINS') != '*' else ['*']
