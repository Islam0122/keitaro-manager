import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { Layout } from '@/components/layout/Layout'
import { ToastProvider } from '@/components/ui/Toast'
import CampaignEditorPage from '@/pages/CampaignEditorPage'
import CampaignsPage from '@/pages/CampaignsPage'
import CreateCampaignPage from '@/pages/CreateCampaignPage'
import LogsPage from '@/pages/LogsPage'
import NotFoundPage from '@/pages/NotFoundPage'
import ResourcesPage from '@/pages/ResourcesPage'
import SettingsPage from '@/pages/SettingsPage'
import StreamsEditorPage from '@/pages/StreamsEditorPage'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/campaigns" replace />} />
            <Route path="campaigns" element={<CampaignsPage />} />
            <Route path="campaigns/new" element={<CreateCampaignPage />} />
            <Route path="campaigns/:id" element={<CampaignEditorPage />} />
            <Route path="campaigns/:id/streams" element={<StreamsEditorPage />} />
            <Route path="resources" element={<ResourcesPage />} />
            <Route path="resources/:tab" element={<ResourcesPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}
