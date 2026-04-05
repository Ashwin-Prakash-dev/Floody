import rasterio, numpy as np
with rasterio.open('data/cache/idukki_jrc_mask.tif') as src:
    d = src.read(1)
    print('dtype:', d.dtype)
    print('min/max:', d.min(), d.max())
    print('unique values:', np.unique(d)[:20])
    print('shape:', d.shape)
    print('nodata:', src.nodata)
