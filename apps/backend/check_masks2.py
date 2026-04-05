import rasterio, numpy as np, warnings
from pathlib import Path

print('Cache files:')
for f in Path('data/cache').glob('*.tif'):
    with rasterio.open(f) as src:
        d = src.read(1).astype(float)
        d[d==0]=float('nan')
        valid = (~np.isnan(d)).sum()
    print(f'  {f.name}: {valid} valid pixels')

with rasterio.open('data/cache/idukki_2019-08-10_event.tif') as src:
    ev = src.read(1).astype(float)
with rasterio.open('data/cache/idukki_2019-03-31_baseline.tif') as src:
    bl = src.read(1).astype(float)

ev[ev<=0]=float('nan')
bl[bl<=0]=float('nan')
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    diff = 10*np.log10(ev) - 10*np.log10(bl)

print('Diff stats: min=%.3f max=%.3f mean=%.3f' % (np.nanmin(diff), np.nanmax(diff), np.nanmean(diff)))
print('Pixels below -3dB:', (diff < -3).sum())

slope30 = Path('data/cache/idukki_slope_mask_30deg.tif')
if slope30.exists():
    with rasterio.open(slope30) as src:
        s = src.read(1).astype(float)
    flooded = diff < -3.0
    slope_mask = s > 0.5
    print('Slope30 masks out:', (flooded & slope_mask).sum(), 'pixels')
    print('Remaining after slope30:', (flooded & ~slope_mask).sum())
else:
    print('slope_30deg file NOT found')
