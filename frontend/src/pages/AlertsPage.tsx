import { useState, useEffect, useCallback } from "react"
import { Download, RefreshCw, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  AlertsTable,
  AlertFilters,
  AlertDetailsDialog,
} from "@/components/alerts"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import api from "@/services/api"

interface Alert {
  id: number
  person_name: string | null
  person_id: number | null
  threat_level: string
  timestamp: string
  acknowledged: boolean
  verified: boolean
  verification_action?: string
  verification_notes?: string
  similarity?: number
}

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [timeRange, setTimeRange] = useState("24h")
  const [threatLevel, setThreatLevel] = useState("all")
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [deleting, setDeleting] = useState(false)

  const fetchAlerts = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number | undefined> = {
        time_range: timeRange,
        limit: 100,
      }
      if (search) params.search = search
      if (threatLevel !== "all") params.threat_level = threatLevel

      const data = await api.alerts.list(params)
      setAlerts(data.alerts || [])
    } catch {
      console.error("Failed to fetch alerts")
    } finally {
      setLoading(false)
    }
  }, [search, timeRange, threatLevel])

  // Debounce search
  useEffect(() => {
    const timeout = setTimeout(() => {
      fetchAlerts()
    }, 300)
    return () => clearTimeout(timeout)
  }, [fetchAlerts])

  const handleViewDetails = (alert: Alert) => {
    setSelectedAlert(alert)
    setDetailsDialogOpen(true)
  }

  const handleAcknowledge = async (alert: Alert) => {
    try {
      await api.alerts.acknowledge(alert.id)
      fetchAlerts()
    } catch {
      console.error("Failed to acknowledge alert")
    }
  }

  const handleVerify = async (alert: Alert, action: string, notes?: string) => {
    try {
      await api.alerts.verify(alert.id, action, notes)
      fetchAlerts()
    } catch {
      console.error("Failed to verify alert")
    }
  }

  const handleDeleteClick = (alert: Alert) => {
    setSelectedAlert(alert)
    setDeleteDialogOpen(true)
  }

  const handleDelete = async () => {
    if (!selectedAlert) return

    setDeleting(true)
    try {
      await api.alerts.delete(selectedAlert.id)
      setDeleteDialogOpen(false)
      setSelectedAlert(null)
      fetchAlerts()
    } catch {
      console.error("Failed to delete alert")
    } finally {
      setDeleting(false)
    }
  }

  const handleExport = () => {
    const params: Record<string, string> = { time_range: timeRange }
    if (search) params.search = search
    if (threatLevel !== "all") params.threat_level = threatLevel

    const url = api.alerts.exportCsv(params)
    window.open(url, "_blank")
  }

  const unacknowledgedCount = alerts.filter((a) => !a.acknowledged).length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Alerts</h1>
          <p className="text-muted-foreground">
            {unacknowledgedCount > 0
              ? `${unacknowledgedCount} unacknowledged alerts`
              : "All alerts acknowledged"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
          <Button variant="outline" onClick={fetchAlerts} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Filters */}
      <AlertFilters
        search={search}
        onSearchChange={setSearch}
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        threatLevel={threatLevel}
        onThreatLevelChange={setThreatLevel}
      />

      {/* Table */}
      <AlertsTable
        alerts={alerts}
        onViewDetails={handleViewDetails}
        onAcknowledge={handleAcknowledge}
        onVerify={(alert) => handleViewDetails(alert)}
        onDelete={handleDeleteClick}
      />

      {/* Summary */}
      <div className="text-sm text-muted-foreground">
        Showing {alerts.length} alerts
      </div>

      {/* Details Dialog */}
      <AlertDetailsDialog
        alert={selectedAlert}
        open={detailsDialogOpen}
        onOpenChange={setDetailsDialogOpen}
        onAcknowledge={handleAcknowledge}
        onVerify={handleVerify}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Alert</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this alert? This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
