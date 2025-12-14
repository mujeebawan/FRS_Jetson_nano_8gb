import { useState, useEffect } from "react"
import { Clock, User, AlertTriangle, Shield, Play } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
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

interface AlertDetailsDialogProps {
  alert: Alert | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onAcknowledge: (alert: Alert) => void
  onVerify: (alert: Alert, action: string, notes?: string) => void
}

export function AlertDetailsDialog({
  alert,
  open,
  onOpenChange,
  onAcknowledge,
  onVerify,
}: AlertDetailsDialogProps) {
  const [hasVideo, setHasVideo] = useState(false)
  const [showVideo, setShowVideo] = useState(false)

  useEffect(() => {
    if (alert && open) {
      // Check if video exists
      api.alerts
        .checkVideoExists(alert.id)
        .then((data) => setHasVideo(data.exists))
        .catch(() => setHasVideo(false))
      setShowVideo(false)
    }
  }, [alert, open])

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
    return new Date(timestamp).toLocaleString()
  }

  if (!alert) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Alert Details</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Snapshot or Video */}
          <div className="relative aspect-video overflow-hidden rounded-lg bg-black">
            {showVideo && hasVideo ? (
              <video
                src={api.alerts.getVideoUrl(alert.id)}
                controls
                autoPlay
                className="h-full w-full object-contain"
              />
            ) : (
              <>
                <img
                  src={api.alerts.getSnapshotUrl(alert.id)}
                  alt="Alert snapshot"
                  className="h-full w-full object-contain"
                />
                {hasVideo && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="absolute bottom-2 right-2"
                    onClick={() => setShowVideo(true)}
                  >
                    <Play className="mr-2 h-4 w-4" />
                    Play Video
                  </Button>
                )}
              </>
            )}
          </div>

          {/* Alert Info */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">
                {alert.person_name || "Unknown Person"}
              </span>
            </div>
            <Badge variant={getThreatBadgeVariant(alert.threat_level)}>
              {alert.threat_level || "Unknown"} Threat
            </Badge>
          </div>

          <Separator />

          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Timestamp</p>
                <p className="font-medium">{formatTime(alert.timestamp)}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Confidence</p>
                <p className="font-medium">
                  {alert.similarity
                    ? `${(alert.similarity * 100).toFixed(1)}%`
                    : "N/A"}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Status</p>
                <p className="font-medium">
                  {alert.verified
                    ? `Verified: ${alert.verification_action}`
                    : alert.acknowledged
                    ? "Acknowledged"
                    : "New"}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Alert ID</p>
                <p className="font-medium">#{alert.id}</p>
              </div>
            </div>
          </div>

          {alert.verification_notes && (
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Verification Notes</p>
              <p className="text-sm">{alert.verification_notes}</p>
            </div>
          )}

          {/* Actions */}
          <Separator />
          <div className="flex flex-wrap gap-2">
            {!alert.acknowledged && (
              <Button
                variant="outline"
                onClick={() => {
                  onAcknowledge(alert)
                  onOpenChange(false)
                }}
              >
                Acknowledge
              </Button>
            )}
            {!alert.verified && (
              <>
                <Button
                  variant="default"
                  onClick={() => {
                    onVerify(alert, "confirmed")
                    onOpenChange(false)
                  }}
                >
                  Confirm Identity
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    onVerify(alert, "false_positive")
                    onOpenChange(false)
                  }}
                >
                  False Positive
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    onVerify(alert, "unclear")
                    onOpenChange(false)
                  }}
                >
                  Unclear
                </Button>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
