import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"

import { ThemeProvider } from "@/providers/ThemeProvider"
import { MainLayout } from "@/components/layout"
import {
  DashboardPage,
  PersonsPage,
  AlertsPage,
  SettingsPage,
} from "@/pages"

function App() {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="persons" element={<PersonsPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}

export default App
