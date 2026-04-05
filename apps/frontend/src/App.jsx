import { useState } from 'react';
import Header from './components/Header.jsx';
import Sidebar from './components/Sidebar.jsx';
import MapPanel from './components/MapPanel.jsx';
import { useFloodAnalysis } from './hooks/useFloodAnalysis.js';
import styles from './App.module.css';

export default function App() {
  const [selectedDistrict, setSelectedDistrict] = useState(null);
  const [eventDate, setEventDate] = useState('2019-08-10');
  const [baselineDate, setBaselineDate] = useState('2019-04-01');
  const [activeIdx, setActiveIdx] = useState(null);

  const { statusMsg, statusType, results, isLoading, runAnalysis } = useFloodAnalysis();

  function handleRun() {
    setActiveIdx(null);
    runAnalysis({ district: selectedDistrict, eventDate, baselineDate });
  }

  function handleSelectDistrict(district) {
    setSelectedDistrict(district);
    setActiveIdx(null);
  }

  function handleSelectSubdivision(idx) {
    setActiveIdx(idx);
  }

  return (
    <div className={styles.app}>
      <Header />
      <Sidebar
        selectedDistrict={selectedDistrict}
        eventDate={eventDate}
        baselineDate={baselineDate}
        isLoading={isLoading}
        statusMsg={statusMsg}
        statusType={statusType}
        results={results}
        activeIdx={activeIdx}
        onSelectDistrict={handleSelectDistrict}
        onEventDate={setEventDate}
        onBaselineDate={setBaselineDate}
        onRun={handleRun}
        onSelectSubdivision={handleSelectSubdivision}
      />
      <MapPanel
        selectedDistrict={selectedDistrict}
        results={results}
        activeIdx={activeIdx}
        onSelectSubdivision={handleSelectSubdivision}
      />
    </div>
  );
}
