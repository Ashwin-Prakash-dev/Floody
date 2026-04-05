import styles from './DistrictSelector.module.css';

const DISTRICTS = [
  { id: 'idukki', label: 'Idukki' },
  { id: 'wayanad', label: 'Wayanad' },
  { id: 'ernakulam', label: 'Ernakulam' },
];

export default function DistrictSelector({ selected, onSelect }) {
  return (
    <div className={styles.section}>
      <div className={styles.label}>District</div>
      <div className={styles.grid}>
        {DISTRICTS.map((d) => (
          <button
            key={d.id}
            className={`${styles.btn} ${selected === d.id ? styles.active : ''}`}
            onClick={() => onSelect(d.id)}
          >
            {d.label}
          </button>
        ))}
      </div>
    </div>
  );
}
