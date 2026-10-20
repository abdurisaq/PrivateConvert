import { Navigate, Route, Routes } from 'react-router-dom';
import './index.css';
import DashboardPage from './pages/DashboardPage';
import Layout from './components/Layout';
import ConvertPage from './pages/ConvertPage';
import JobsPage from './pages/JobsPage';
import ProcessingPage from './pages/ProcessingPage';

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/dashboard" element={<Navigate to="/" replace />} />
        <Route path="/convert" element={<ConvertPage />} />
        <Route path="/process" element={<ProcessingPage />} />
        <Route path="/jobs" element={<JobsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
