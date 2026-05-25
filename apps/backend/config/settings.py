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
    'thiruvananthapuram': {'bbox': [76.70, 8.30, 77.40, 8.90], 'display': 'Thiruvananthapuram'},
    'kollam':             {'bbox': [76.50, 8.70, 77.30, 9.30], 'display': 'Kollam'},
    'pathanamthitta':     {'bbox': [76.60, 9.10, 77.30, 9.70], 'display': 'Pathanamthitta'},
    'alappuzha':          {'bbox': [76.10, 9.10, 76.70, 9.70], 'display': 'Alappuzha'},
    'kottayam':           {'bbox': [76.40, 9.40, 77.10, 10.00], 'display': 'Kottayam'},
    'idukki':             {'bbox': [76.60, 9.60, 77.40, 10.40], 'display': 'Idukki'},
    'ernakulam':          {'bbox': [76.10, 9.80, 76.80, 10.30], 'display': 'Ernakulam'},
    'thrissur':           {'bbox': [76.00, 10.10, 76.90, 10.80], 'display': 'Thrissur'},
    'palakkad':           {'bbox': [76.30, 10.40, 77.00, 11.20], 'display': 'Palakkad'},
    'malappuram':         {'bbox': [75.80, 10.70, 76.60, 11.30], 'display': 'Malappuram'},
    'kozhikode':          {'bbox': [75.60, 11.10, 76.30, 11.70], 'display': 'Kozhikode'},
    'wayanad':            {'bbox': [75.70, 11.40, 76.40, 11.90], 'display': 'Wayanad'},
    'kannur':             {'bbox': [75.20, 11.70, 76.20, 12.30], 'display': 'Kannur'},
    'kasaragod':          {'bbox': [74.80, 12.20, 75.70, 12.80], 'display': 'Kasaragod'},
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
