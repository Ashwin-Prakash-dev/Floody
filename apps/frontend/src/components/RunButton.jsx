import styles from './RunButton.module.css';

export default function RunButton({ district, isLoading, onClick }) {
  const disabled = !district || isLoading;

  let label;
  if (isLoading) label = 'Analysing…';
  else if (!district) label = 'Select a district';
  else label = `Analyse ${district.charAt(0).toUpperCase() + district.slice(1)}`;

  return (
    <div className={styles.section}>
      <button
        className={`${styles.btn} ${isLoading ? styles.loading : ''}`}
        disabled={disabled}
        onClick={onClick}
      >
        {label}
      </button>
    </div>
  );
}
