import { HashRouter, Routes, Route } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { HomePage } from '@/components/index/HomePage'
import { WorkflowsPage } from '@/components/workflow/WorkflowsPage'
import { NewWorkflowPage } from '@/components/workflow/NewWorkflowPage'
import { WorkflowDetailPage } from '@/components/workflow/WorkflowDetailPage'
import { IndexPage } from '@/components/index/IndexPage'
import { SettingsPage } from '@/components/settings/SettingsPage'

export function App() {
  return (
    <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/workflow/new" element={<NewWorkflowPage />} />
          <Route path="/workflow/:threadId" element={<WorkflowDetailPage />} />
          <Route path="/index" element={<IndexPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </HashRouter>
  )
}
