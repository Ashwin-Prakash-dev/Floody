import styles from './StatsGrid.module.css';

export default function StatsGrid({ results }) {
  if (!results) return null;

  return (
    <div className={styles.grid}>
      <div className={styles.cell}>
        <div className={styles.value}>{results.total_flooded_ha.toFixed(1)}</div>
        <div className={styles.label}>Flooded (ha)</div>
      </div>
      <div className={styles.cell}>
        <div className={`${styles.value} ${styles.warn}`}>
          {results.flood_pct_overall.toFixed(2)}%
        </div>
        <div className={styles.label}>% Affected</div>
      </div>
      <div className={styles.cell}>
        <div className={styles.value}>{results.total_area_ha.toFixed(0)}</div>
        <div className={styles.label}>Total Area (ha)</div>
      </div>
    </div>
  );
}
