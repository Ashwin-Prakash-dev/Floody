import rasterio, numpy as np
from analysis.flood_detector import _read_raster, _reproject_to_match, RasterData
from config.settings import CACHE_DIR

jrc_path = CACHE_DIR / 'idukki_jrc_mask.tif'
event_path = CACHE_DIR / 'idukki_2019-08-10_event.tif'

print('--- Raw JRC read ---')
with rasterio.open(jrc_path) as src:
    raw = src.read(1).astype(float)
    jrc_transform = src.transform
    jrc_crs = src.crs.to_string()
print('raw 0s:', (raw==0).sum())
print('raw 1s:', (raw==1).sum())

print('--- After _read_raster (zeros become NaN) ---')
jrc_rd = _read_raster(jrc_path)
print('NaN:', np.isnan(jrc_rd.data).sum())
print('1s:', (jrc_rd.data==1).sum())
print('0s:', (jrc_rd.data==0).sum())

print('--- After reproject ---')
with rasterio.open(event_path) as src:
    ev = src.read(1).astype(float)
    ev_transform = src.transform
    ev_crs = src.crs.to_string()
target = RasterData(data=np.zeros((1781,1754), dtype=np.float32), transform=ev_transform, crs=ev_crs)
matched = _reproject_to_match(jrc_rd, target)
print('NaN after reproject:', np.isnan(matched.data).sum())
print('1s after reproject:', (matched.data==1).sum())
print('>0.5 after reproject:', (matched.data>0.5).sum())
