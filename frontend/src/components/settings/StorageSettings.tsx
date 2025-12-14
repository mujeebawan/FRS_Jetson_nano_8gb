import { useState, useEffect } from "react"
import { HardDrive, Trash2, Loader2 } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import api from "@/services/api"

interface StorageInfo {
  total_gb?: number
  used_gb?: number
  free_gb?: number
  percent_used?: number
  snapshots_count?: number
  clips_count?: number
  alerts_count?: number
}

export function StorageSettings() {
  const [storage, setStorage] = useState<StorageInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [cleaning, setCleaning] = useState(false)
  const [days, setDays] = useState(30)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchStorage()
  }, [])

  const fetchStorage = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.system.storage()
      setStorage(data)
    } catch (err) {
      console.error("Failed to fetch storage info", err)
      setError("Failed to load storage information")
    } finally {
      setLoading(false)
    }
  }

  const handleCleanup = async () => {
    setCleaning(true)
    try {
      await api.system.cleanupStorage(days)
      await fetchStorage()
    } catch {
      console.error("Failed to cleanup storage")
    } finally {
      setCleaning(false)
    }
  }

  const getUsageColor = (percent: number) => {
    if (percent > 90) return "bg-destructive"
    if (percent > 70) return "bg-warning"
    return "bg-primary"
  }

  const formatGB = (value?: number) => {
    if (value === undefined || value === null) return "0.0"
    return value.toFixed(1)
  }

  const percentUsed = storage?.percent_used ?? 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HardDrive className="h-5 w-5" />
          Storage Management
        </CardTitle>
        <CardDescription>
          Monitor and manage storage usage
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {loading ? (
          <div className="flex h-32 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : error ? (
          <p className="text-center text-muted-foreground">
            {error}
          </p>
        ) : storage ? (
          <>
            {/* Usage Bar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Storage Usage</span>
                <span className="font-medium">
                  {formatGB(storage.used_gb)} / {formatGB(storage.total_gb)} GB
                </span>
              </div>
              <Progress
                value={percentUsed}
                className={`h-3 ${getUsageColor(percentUsed)}`}
              />
              <p className="text-xs text-muted-foreground">
                {formatGB(storage.free_gb)} GB free ({(100 - percentUsed).toFixed(0)}%)
              </p>
            </div>

            {/* File Counts */}
            <div className="grid grid-cols-3 gap-4">
              {storage.snapshots_count !== undefined && (
                <div className="rounded-lg border p-3 text-center">
                  <p className="text-2xl font-bold">{storage.snapshots_count}</p>
                  <p className="text-xs text-muted-foreground">Snapshots</p>
                </div>
              )}
              {storage.clips_count !== undefined && (
                <div className="rounded-lg border p-3 text-center">
                  <p className="text-2xl font-bold">{storage.clips_count}</p>
                  <p className="text-xs text-muted-foreground">Video Clips</p>
                </div>
              )}
              {storage.alerts_count !== undefined && (
                <div className="rounded-lg border p-3 text-center">
                  <p className="text-2xl font-bold">{storage.alerts_count}</p>
                  <p className="text-xs text-muted-foreground">Alert Records</p>
                </div>
              )}
            </div>

            {/* Cleanup */}
            <div className="rounded-lg border p-4 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="cleanupDays">Delete data older than (days)</Label>
                <Input
                  id="cleanupDays"
                  type="number"
                  value={days}
                  onChange={(e) => setDays(parseInt(e.target.value) || 1)}
                  min={1}
                  max={365}
                />
              </div>
              <Button
                variant="destructive"
                onClick={handleCleanup}
                disabled={cleaning}
              >
                {cleaning ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="mr-2 h-4 w-4" />
                )}
                Cleanup Old Data
              </Button>
            </div>
          </>
        ) : (
          <p className="text-center text-muted-foreground">
            No storage information available
          </p>
        )}
      </CardContent>
    </Card>
  )
}
