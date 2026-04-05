import rasterio, numpy as np, warnings

with rasterio.open('data/cache/idukki_2019-08-10_event.tif') as src:
    ev = src.read(1).astype(float)
with rasterio.open('data/cache/idukki_2019-03-31_baseline.tif') as src:
    bl = src.read(1).astype(float)
with rasterio.open('data/cache/idukki_jrc_mask.tif') as src:
    jrc = src.read(1).astype(float)
with rasterio.open('data/cache/idukki_slope_mask_5deg.tif') as src:
    slope = src.read(1).astype(float)

ev[ev<=0]=float('nan')
bl[bl<=0]=float('nan')
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    diff = 10*np.log10(ev) - 10*np.log10(bl)

flooded_raw = diff < -3.0
print('Raw flooded pixels (before masks):', flooded_raw.sum())

jrc_mask = jrc > 0.5
slope_mask = slope > 0.5
print('JRC masked pixels:', (flooded_raw & jrc_mask).sum())
print('Slope masked pixels:', (flooded_raw & slope_mask).sum())
print('After JRC removal:', (flooded_raw & ~jrc_mask).sum())
print('After slope removal:', (flooded_raw & ~jrc_mask & ~slope_mask).sum())
print('JRC unique values:', np.unique(jrc[~np.isnan(jrc)])[:10])
print('Slope unique values:', np.unique(slope[~np.isnan(slope)])[:10])
