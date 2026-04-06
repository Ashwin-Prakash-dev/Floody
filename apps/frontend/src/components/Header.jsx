import styles from './Header.module.css';

export default function Header({ isDark, onToggleTheme }) {
  return (
    <header className={styles.header}>
      <div className={styles.logo}>
        <div className={styles.logoIcon} />
        Kerala <span>SAR</span> Flood Monitor
      </div>
      <div className={styles.headerTag}>SENTINEL-1 · DESCENDING · VV</div>
      <button className={styles.themeToggle} onClick={onToggleTheme} title="Toggle theme">
        {isDark ? '☀' : '☾'}
      </button>
      <div className={styles.statusDot} title="API online" />
    </header>
  );
}
