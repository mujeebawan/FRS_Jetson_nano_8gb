import { useState, useEffect } from "react"

import {
  StatsOverview,
  LiveStreamCard,
  RecentAlertsCard,
  SystemStatusCard,
} from "@/components/dashboard"
import api from "@/services/api"

export function DashboardPage() {
  const [personCount, setPersonCount] = useState(0)
  const [alertCount, setAlertCount] = useState(0)
  const [fps, setFps] = useState(0)
  const [gpuUsage, setGpuUsage] = useState(0)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        // Fetch person count
        const personsData = await api.persons.list()
        setPersonCount(personsData.length || 0)
      } catch {
        // Ignore errors
      }

      try {
        // Fetch alert count
        const alertsData = await api.alerts.list({
          acknowledged: false,
          limit: 100,
        })
        setAlertCount(alertsData.alerts?.length || 0)
      } catch {
        // Ignore errors
      }

      try {
        // Fetch stream status
        const streamData = await api.stream.status()
        setFps(streamData.fps || 0)
      } catch {
        // Ignore errors
      }

      try {
        // Fetch GPU usage
        const resourcesData = await api.system.resources()
        setGpuUsage(resourcesData.gpu?.utilization || 0)
      } catch {
        // Ignore errors
      }
    }

    fetchStats()
    const interval = setInterval(fetchStats, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <StatsOverview
        personCount={personCount}
        alertCount={alertCount}
        fps={fps}
        gpuUsage={gpuUsage}
      />

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Live Stream - Takes 2 columns */}
        <LiveStreamCard />

        {/* Recent Alerts */}
        <RecentAlertsCard />
      </div>

      {/* System Status - Full width */}
      <div className="grid gap-6 lg:grid-cols-2">
        <SystemStatusCard />
      </div>
    </div>
  )
}
