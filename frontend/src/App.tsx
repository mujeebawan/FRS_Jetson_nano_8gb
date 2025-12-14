import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"

import { ThemeProvider } from "@/providers/ThemeProvider"
import { AuthProvider } from "@/contexts/AuthContext"
import { ProtectedRoute } from "@/components/auth/ProtectedRoute"
import { MainLayout } from "@/components/layout"
import { LoginPage } from "@/pages/LoginPage"
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
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="persons" element={<PersonsPage />} />
              <Route path="alerts" element={<AlertsPage />} />
              <Route
                path="settings"
                element={
                  <ProtectedRoute requireAdmin>
                    <SettingsPage />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
