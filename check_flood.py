import rasterio, numpy as np, warnings
with rasterio.open('data/cache/idukki_2019-08-10_event.tif') as src:
    ev = src.read(1).astype(float)
    transform = src.transform
with rasterio.open('data/cache/idukki_2019-03-31_baseline.tif') as src:
    bl = src.read(1).astype(float)
ev[ev<=0]=float('nan')
bl[bl<=0]=float('nan')
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    diff = 10*np.log10(ev) - 10*np.log10(bl)
flooded = diff < -3.0
rows,cols = np.where(flooded)
for r,c in zip(rows[:20],cols[:20]):
    lon = transform.c + c*transform.a
    lat = transform.f + r*transform.e
    print(f'  flooded pixel at lat={lat:.4f} lon={lon:.4f} diff={diff[r,c]:.2f}dB')
print(f'Total flooded pixels: {flooded.sum()}')
