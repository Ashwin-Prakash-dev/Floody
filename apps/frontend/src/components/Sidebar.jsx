import DistrictSelector from './DistrictSelector.jsx';
import DateRangePicker from './DateRangePicker.jsx';
import RunButton from './RunButton.jsx';
import StatusBar from './StatusBar.jsx';
import StatsGrid from './StatsGrid.jsx';
import SubdivisionList from './SubdivisionList.jsx';
import styles from './Sidebar.module.css';

export default function Sidebar({
  selectedDistrict,
  eventDate,
  baselineDate,
  isLoading,
  statusMsg,
  statusType,
  results,
  activeIdx,
  onSelectDistrict,
  onEventDate,
  onBaselineDate,
  onRun,
  onSelectSubdivision,
}) {
  return (
    <aside className={styles.sidebar}>
      <DistrictSelector selected={selectedDistrict} onSelect={onSelectDistrict} />
      <DateRangePicker
        eventDate={eventDate}
        baselineDate={baselineDate}
        onEventDate={onEventDate}
        onBaselineDate={onBaselineDate}
      />
      <RunButton district={selectedDistrict} isLoading={isLoading} onClick={onRun} />
      <StatusBar message={statusMsg} type={statusType} isLoading={isLoading} />
      <StatsGrid results={results} />
      <SubdivisionList
        results={results}
        activeIdx={activeIdx}
        onSelect={onSelectSubdivision}
        isLoading={isLoading}
      />
    </aside>
  );
}
