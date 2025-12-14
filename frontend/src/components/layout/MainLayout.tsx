import { useState, useEffect } from "react"
import { Outlet } from "react-router-dom"

import { AppSidebar } from "./AppSidebar"
import { Header } from "./Header"
import { TooltipProvider } from "@/components/ui/tooltip"
import api from "@/services/api"

export function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [alertCount, setAlertCount] = useState(0)
  const [streamStatus, setStreamStatus] = useState<"active" | "inactive" | "error">("inactive")
  const [cameraStatus, setCameraStatus] = useState<"connected" | "disconnected" | "error">("disconnected")

  // Fetch status periodically
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        // Fetch stream status
        const streamData = await api.stream.status()
        setStreamStatus(streamData.is_running ? "active" : "inactive")
      } catch {
        setStreamStatus("error")
      }

      try {
        // Fetch camera status
        const cameraData = await api.system.cameraInfo()
        setCameraStatus(cameraData.connected ? "connected" : "disconnected")
      } catch {
        setCameraStatus("error")
      }

      try {
        // Fetch alert count (unacknowledged)
        const alertsData = await api.alerts.list({ acknowledged: false, limit: 100 })
        setAlertCount(alertsData.alerts?.length || 0)
      } catch {
        // Ignore alert fetch errors
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 5000) // Update every 5 seconds

    return () => clearInterval(interval)
  }, [])

  // Handle keyboard shortcut for sidebar toggle
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "b") {
        e.preventDefault()
        setCollapsed((prev) => !prev)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  return (
    <TooltipProvider>
      <div className="flex h-screen overflow-hidden bg-background">
        <AppSidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed(!collapsed)}
          alertCount={alertCount}
          streamStatus={streamStatus}
          cameraStatus={cameraStatus}
        />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Header />
          <main className="flex-1 overflow-auto p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </TooltipProvider>
  )
}
