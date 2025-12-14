import { useState, useEffect } from "react"
import { Cpu, HardDrive, Thermometer, Zap } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import api from "@/services/api"

interface Resources {
  cpu: {
    percent: number
    cores: number
    load_avg: number[]
  }
  memory: {
    used_gb: number
    total_gb: number
    percent: number
  }
  gpu?: {
    utilization: number
    memory_used_mb: number
    memory_total_mb: number
    temperature: number
  }
  power?: {
    current_mw: number
  }
}

export function SystemStatusCard() {
  const [resources, setResources] = useState<Resources | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchResources = async () => {
      try {
        const data = await api.system.resources()
        setResources(data)
      } catch {
        console.error("Failed to fetch resources")
      } finally {
        setLoading(false)
      }
    }

    fetchResources()
    const interval = setInterval(fetchResources, 3000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">System Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-48 items-center justify-center">
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const getProgressColor = (value: number) => {
    if (value > 80) return "bg-destructive"
    if (value > 60) return "bg-warning"
    return "bg-primary"
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">System Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* CPU */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              CPU
            </span>
            <span className="font-medium">{resources?.cpu?.percent?.toFixed(0) || 0}%</span>
          </div>
          <Progress
            value={resources?.cpu?.percent || 0}
            className={`h-2 ${getProgressColor(resources?.cpu?.percent || 0)}`}
          />
        </div>

        {/* GPU */}
        {resources?.gpu && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-muted-foreground" />
                GPU
              </span>
              <span className="font-medium">{resources.gpu.utilization?.toFixed(0) || 0}%</span>
            </div>
            <Progress
              value={resources.gpu.utilization || 0}
              className={`h-2 ${getProgressColor(resources.gpu.utilization || 0)}`}
            />
          </div>
        )}

        {/* Memory */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2">
              <HardDrive className="h-4 w-4 text-muted-foreground" />
              Memory
            </span>
            <span className="font-medium">
              {resources?.memory?.used_gb?.toFixed(1) || 0} / {resources?.memory?.total_gb?.toFixed(1) || 0} GB
            </span>
          </div>
          <Progress
            value={resources?.memory?.percent || 0}
            className={`h-2 ${getProgressColor(resources?.memory?.percent || 0)}`}
          />
        </div>

        {/* Temperature */}
        {resources?.gpu?.temperature !== undefined && (
          <div className="flex items-center justify-between rounded-lg border p-3">
            <span className="flex items-center gap-2 text-sm">
              <Thermometer className="h-4 w-4 text-muted-foreground" />
              Temperature
            </span>
            <span
              className={`font-medium ${
                resources.gpu.temperature > 70
                  ? "text-destructive"
                  : resources.gpu.temperature > 50
                  ? "text-warning"
                  : "text-success"
              }`}
            >
              {resources.gpu.temperature}°C
            </span>
          </div>
        )}

        {/* Power */}
        {resources?.power?.current_mw !== undefined && (
          <div className="flex items-center justify-between rounded-lg border p-3">
            <span className="flex items-center gap-2 text-sm">
              <Zap className="h-4 w-4 text-muted-foreground" />
              Power
            </span>
            <span className="font-medium">
              {(resources.power.current_mw / 1000).toFixed(1)} W
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
