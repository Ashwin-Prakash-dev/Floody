import styles from './StatusBar.module.css';

export default function StatusBar({ message, type, isLoading }) {
  const showSpinner = isLoading && message.startsWith('Running');

  return (
    <div className={`${styles.bar} ${type ? styles[type] : ''}`}>
      {showSpinner && <div className="spinner" />}
      <span>{message}</span>
    </div>
  );
}
