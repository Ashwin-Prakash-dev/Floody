import styles from './DateRangePicker.module.css';

export default function DateRangePicker({ eventDate, baselineDate, onEventDate, onBaselineDate }) {
  return (
    <div className={styles.section}>
      <div className={styles.label}>Date Range</div>
      <div className={styles.row}>
        <div className={styles.field}>
          <label htmlFor="event-date">Event Date</label>
          <input
            id="event-date"
            type="date"
            value={eventDate}
            onChange={(e) => onEventDate(e.target.value)}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="baseline-date">Baseline Date</label>
          <input
            id="baseline-date"
            type="date"
            value={baselineDate}
            onChange={(e) => onBaselineDate(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
