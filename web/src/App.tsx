import { Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { RunBrowser } from '@/pages/RunBrowser'
import { RunDetail } from '@/pages/RunDetail'
import { LiveMonitor } from '@/pages/LiveMonitor'
import { RunLauncher } from '@/pages/RunLauncher'
import { QABrowser } from '@/pages/QABrowser'
import { QARunDetail } from '@/pages/QARunDetail'
import { Comparison } from '@/pages/Comparison'
import { PromptRunner } from '@/pages/PromptRunner'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="runs" element={<RunBrowser />} />
        <Route path="runs/:runId" element={<RunDetail />} />
        <Route path="runs/:runId/live" element={<LiveMonitor />} />
        <Route path="launch" element={<RunLauncher />} />
        <Route path="qa" element={<QABrowser />} />
        <Route path="qa/:runId" element={<QARunDetail />} />
        <Route path="compare" element={<Comparison />} />
        <Route path="prompt" element={<PromptRunner />} />
      </Route>
    </Routes>
  )
}

export default App
