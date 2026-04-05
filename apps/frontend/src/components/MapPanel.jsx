import { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, ZoomControl, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import MapLegend from './MapLegend.jsx';
import styles from './MapPanel.module.css';

const DISTRICT_CENTERS = {
  idukki:    [10.0, 77.0],
  wayanad:   [11.65, 76.05],
  ernakulam: [10.05, 76.45],
};

function floodColor(pct) {
  if (pct > 30) return '#ff6b35';
  if (pct > 10) return '#ffaa00';
  if (pct > 0) return '#00c8ff';
  return 'rgba(255,255,255,0.15)';
}

function MapController({ selectedDistrict, results, activeIdx, layerRefs }) {
  const map = useMap();
  const prevResultsRef = useRef(null);

  useEffect(() => {
    if (!selectedDistrict) return;
    const center = DISTRICT_CENTERS[selectedDistrict];
    if (center) map.flyTo(center, 9, { duration: 1.2 });
  }, [selectedDistrict, map]);

  useEffect(() => {
    if (!results || results === prevResultsRef.current) return;
    prevResultsRef.current = results;

    const features = results.subdivisions.filter((s) => s.geometry);
    if (!features.length) return;

    const fc = {
      type: 'FeatureCollection',
      features: features.map((s) => ({ type: 'Feature', geometry: s.geometry, properties: {} })),
    };
    const bounds = L.geoJSON(fc).getBounds();
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.1));
  }, [results, map]);

  useEffect(() => {
    if (activeIdx === null || !results) return;
    const layer = layerRefs.current[activeIdx];
    if (!layer) return;
    layer.openPopup();
    const bounds = layer.getBounds();
    if (bounds.isValid()) map.flyToBounds(bounds.pad(0.3), { duration: 0.8 });
  }, [activeIdx, results, map, layerRefs]);

  return null;
}

export default function MapPanel({ selectedDistrict, results, activeIdx, onSelectSubdivision }) {
  const layerRefs = useRef([]);
  const sorted = results
    ? [...results.subdivisions].sort((a, b) => b.flood_pct - a.flood_pct)
    : [];

  // Reset layer refs when results change
  if (!results) layerRefs.current = [];

  return (
    <div className={styles.wrap}>
      <MapContainer
        center={[10.1, 76.8]}
        zoom={8}
        zoomControl={false}
        className={styles.map}
      >
        <ZoomControl position="topright" />
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution="© OpenStreetMap © CartoDB"
          subdomains="abcd"
          maxZoom={19}
        />

        <MapController
          selectedDistrict={selectedDistrict}
          results={results}
          activeIdx={activeIdx}
          layerRefs={layerRefs}
        />

        {sorted.map((s, i) => {
          if (!s.geometry) return null;
          const color = floodColor(s.flood_pct);
          return (
            <GeoJSON
              key={`${results.job_id}-${i}`}
              data={s.geometry}
              style={{
                fillColor: color,
                fillOpacity: s.flood_pct > 0 ? 0.45 : 0.08,
                color,
                weight: 1,
                opacity: 0.6,
              }}
              onEachFeature={(_, layer) => {
                layerRefs.current[i] = layer;
                layer.bindPopup(`
                  <div class="popup-title">${s.subdivision}</div>
                  <div class="popup-row"><span>Flooded</span><span class="popup-val">${s.flooded_ha} ha</span></div>
                  <div class="popup-row"><span>Total</span><span>${s.total_ha} ha</span></div>
                  <div class="popup-row"><span>Flood %</span><span class="popup-val warn">${s.flood_pct.toFixed(1)}%</span></div>
                  <div class="popup-row"><span>District</span><span>${s.district}</span></div>
                `);
                layer.on('click', () => onSelectSubdivision(i));
              }}
            />
          );
        })}
      </MapContainer>

      {results && <MapLegend />}
    </div>
  );
}
