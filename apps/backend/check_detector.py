import numpy as np, warnings
from pathlib import Path
from analysis.flood_detector import load_and_align, to_db, compute_difference, build_flood_mask, _load_ancillary_mask
from config.settings import CACHE_DIR

event_tif = CACHE_DIR / 'idukki_2019-08-10_event.tif'
baseline_tif = CACHE_DIR / 'idukki_2019-04-01_baseline.tif'
slope_tif = CACHE_DIR / 'idukki_slope_mask_30deg.tif'
jrc_tif = CACHE_DIR / 'idukki_jrc_mask.tif'

event_raw, baseline_raw = load_and_align(event_tif, baseline_tif)
event_db = to_db(event_raw)
baseline_db = to_db(baseline_raw)
diff = compute_difference(event_db, baseline_db)

print('Diff min/max/mean:', round(float(np.nanmin(diff.data)),3), round(float(np.nanmax(diff.data)),3), round(float(np.nanmean(diff.data)),3))
print('NaN in diff:', int(np.isnan(diff.data).sum()), '/', diff.data.size)
print('Pixels below -3dB:', int((diff.data < -3.0).sum()))

flooded = (diff.data < -3.0) & ~np.isnan(diff.data)
print('Raw flooded:', flooded.sum())

jrc = _load_ancillary_mask(jrc_tif, diff.data.shape, diff.transform, diff.crs)
print('JRC mask True pixels:', jrc.sum())
print('JRC removes:', (flooded & jrc).sum())
flooded2 = flooded & ~jrc
print('After JRC:', flooded2.sum())

slope = _load_ancillary_mask(slope_tif, diff.data.shape, diff.transform, diff.crs)
print('Slope mask True pixels:', slope.sum())
print('Slope removes:', (flooded2 & slope).sum())
flooded3 = flooded2 & ~slope
print('After slope:', flooded3.sum())

final = build_flood_mask(diff, -3.0, jrc_tif, slope_tif)
print('build_flood_mask result:', int(np.nansum(final.data)))
