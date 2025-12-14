import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import { AlertTriangle, ArrowRight, Clock } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { ScrollArea } from "@/components/ui/scroll-area"
import api from "@/services/api"

interface Alert {
  id: number
  person_name: string | null
  person_id: number | null
  threat_level: string
  timestamp: string
  acknowledged: boolean
}

export function RecentAlertsCard() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const data = await api.alerts.list({
          limit: 5,
          time_range: "24h",
        })
        setAlerts(data.alerts || [])
      } catch {
        console.error("Failed to fetch alerts")
      } finally {
        setLoading(false)
      }
    }

    fetchAlerts()
    const interval = setInterval(fetchAlerts, 10000)
    return () => clearInterval(interval)
  }, [])

  const getThreatBadgeVariant = (level: string) => {
    switch (level?.toLowerCase()) {
      case "high":
        return "destructive"
      case "medium":
        return "warning"
      case "low":
        return "success"
      default:
        return "secondary"
    }
  }

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 60000) return "Just now"
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return date.toLocaleDateString()
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Recent Alerts</CardTitle>
          <Badge variant="outline">{alerts.length} today</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex h-48 items-center justify-center">
            <p className="text-muted-foreground">Loading...</p>
          </div>
        ) : alerts.length === 0 ? (
          <div className="flex h-48 flex-col items-center justify-center text-muted-foreground">
            <AlertTriangle className="mb-2 h-8 w-8" />
            <p>No recent alerts</p>
          </div>
        ) : (
          <>
            <ScrollArea className="h-48">
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="flex items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
                  >
                    <Avatar className="h-10 w-10">
                      <AvatarImage
                        src={api.alerts.getSnapshotUrl(alert.id)}
                        alt={alert.person_name || "Unknown"}
                      />
                      <AvatarFallback>
                        {alert.person_name?.[0] || "?"}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <p className="truncate font-medium">
                        {alert.person_name || "Unknown Person"}
                      </p>
                      <p className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {formatTime(alert.timestamp)}
                      </p>
                    </div>
                    <Badge variant={getThreatBadgeVariant(alert.threat_level)}>
                      {alert.threat_level || "Unknown"}
                    </Badge>
                  </div>
                ))}
              </div>
            </ScrollArea>
            <Button variant="ghost" className="mt-4 w-full" asChild>
              <Link to="/alerts">
                View All Alerts
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  )
}
