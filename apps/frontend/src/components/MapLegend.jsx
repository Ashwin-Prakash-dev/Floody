import styles from './MapLegend.module.css';

const ENTRIES = [
  { color: '#ff6b35', label: '>30% flooded' },
  { color: '#ffaa00', label: '10–30% flooded' },
  { color: '#00c8ff', label: '<10% flooded' },
  { color: 'rgba(255,255,255,0.08)', label: 'No flooding', border: '#1e2730' },
];

export default function MapLegend() {
  return (
    <div className={styles.legend}>
      <div className={styles.title}>Flood Intensity</div>
      {ENTRIES.map((e) => (
        <div key={e.label} className={styles.row}>
          <div
            className={styles.swatch}
            style={{
              background: e.color,
              border: e.border ? `1px solid ${e.border}` : undefined,
            }}
          />
          {e.label}
        </div>
      ))}
    </div>
  );
}
