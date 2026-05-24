import styles from './DistrictSelector.module.css';

const DISTRICTS = [
  { id: 'thiruvananthapuram', label: 'Thiruvananthapuram' },
  { id: 'kollam',             label: 'Kollam' },
  { id: 'pathanamthitta',     label: 'Pathanamthitta' },
  { id: 'alappuzha',          label: 'Alappuzha' },
  { id: 'kottayam',           label: 'Kottayam' },
  { id: 'idukki',             label: 'Idukki' },
  { id: 'ernakulam',          label: 'Ernakulam' },
  { id: 'thrissur',           label: 'Thrissur' },
  { id: 'palakkad',           label: 'Palakkad' },
  { id: 'malappuram',         label: 'Malappuram' },
  { id: 'kozhikode',          label: 'Kozhikode' },
  { id: 'wayanad',            label: 'Wayanad' },
  { id: 'kannur',             label: 'Kannur' },
  { id: 'kasaragod',          label: 'Kasaragod' },
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