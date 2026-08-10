import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Academy from './pages/Academy'
import AcademyLesson from './pages/AcademyLesson'
import Connections from './pages/Connections'
import Dashboard from './pages/Dashboard'
import Fleet from './pages/Fleet'
import Graph from './pages/Graph'
import Observability from './pages/Observability'
import RunDetailPage from './pages/RunDetail'
import Runs from './pages/Runs'
import Workbench from './pages/Workbench'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/fleet" element={<Fleet />} />
        <Route path="/agents/:agentId" element={<Workbench />} />
        <Route path="/runs" element={<Runs />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/observability" element={<Observability />} />
        <Route path="/academy" element={<Academy />} />
        <Route path="/academy/:agentId" element={<AcademyLesson />} />
        <Route path="/graph" element={<Graph />} />
        <Route path="/connections" element={<Connections />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}
