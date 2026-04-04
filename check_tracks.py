import ee, os
ee.Initialize(project='rotterdam-484003')
os.environ['GEE_USE_ADC'] = 'true'
s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(ee.Geometry.Rectangle([76.6, 9.6, 77.4, 10.4])).filter(ee.Filter.eq('instrumentMode', 'IW')).select('VV')
event_img = s1.filterDate('2019-08-09', '2019-08-11').first()
baseline_img = s1.filterDate('2019-03-30', '2019-04-01').first()
ei = event_img.getInfo()['properties']
bi = baseline_img.getInfo()['properties']
print('Event track:', ei.get('relativeOrbitNumber_start'), '| pass:', ei.get('orbitProperties_pass'))
print('Baseline track:', bi.get('relativeOrbitNumber_start'), '| pass:', bi.get('orbitProperties_pass'))
