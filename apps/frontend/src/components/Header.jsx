import styles from './Header.module.css';

export default function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.logo}>
        <div className={styles.logoIcon} />
        Kerala <span>SAR</span> Flood Monitor
      </div>
      <div className={styles.headerTag}>SENTINEL-1 · DESCENDING · VV</div>
      <div className={styles.statusDot} title="API online" />
    </header>
  );
}
