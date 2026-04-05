import { useEffect, useRef } from 'react';
import styles from './SubdivisionList.module.css';

function floodColor(pct) {
  if (pct > 30) return '#ff6b35';
  if (pct > 10) return '#ffaa00';
  if (pct > 0) return '#00c8ff';
  return 'rgba(255,255,255,0.15)';
}

function SubdivisionItem({ subdivision, index, isActive, onClick }) {
  const itemRef = useRef(null);
  const barRef = useRef(null);
  const color = floodColor(subdivision.flood_pct);

  // Animate bar fill on mount with staggered delay
  useEffect(() => {
    const delay = index * 40;
    const timer = setTimeout(() => {
      if (barRef.current) {
        barRef.current.style.width = Math.min(subdivision.flood_pct, 100) + '%';
      }
    }, delay);
    return () => clearTimeout(timer);
  }, [subdivision.flood_pct, index]);

  // Scroll into view when active
  useEffect(() => {
    if (isActive && itemRef.current) {
      itemRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [isActive]);

  return (
    <div
      ref={itemRef}
      className={`${styles.item} ${isActive ? styles.active : ''}`}
      onClick={onClick}
    >
      <div className={styles.barWrap}>
        <div className={styles.name}>{subdivision.subdivision}</div>
        <div className={styles.barBg}>
          <div
            ref={barRef}
            className={styles.barFill}
            style={{ width: '0%', background: color }}
          />
        </div>
        <div className={styles.ha}>
          {subdivision.flooded_ha} ha flooded of {subdivision.total_ha} ha
        </div>
      </div>
      <div className={styles.pct} style={{ color }}>
        {subdivision.flood_pct.toFixed(1)}%
      </div>
    </div>
  );
}

export default function SubdivisionList({ results, activeIdx, onSelect, isLoading }) {
  if (isLoading) {
    return (
      <div className={styles.list}>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>◎</div>
          <p>ANALYSIS RUNNING<br />PLEASE WAIT</p>
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <div className={styles.list}>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>◎</div>
          <p>NO DATA LOADED<br />SELECT DISTRICT<br />AND RUN ANALYSIS</p>
        </div>
      </div>
    );
  }

  const sorted = [...results.subdivisions].sort((a, b) => b.flood_pct - a.flood_pct);

  return (
    <div className={styles.list}>
      {sorted.map((s, i) => (
        <SubdivisionItem
          key={`${s.subdivision}-${i}`}
          subdivision={s}
          index={i}
          isActive={activeIdx === i}
          onClick={() => onSelect(i)}
        />
      ))}
    </div>
  );
}
