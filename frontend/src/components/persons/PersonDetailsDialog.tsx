import { useState, useEffect } from "react"
import { Calendar, Shield, FileText, Hash, Clock, Eye } from "lucide-react"

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import api from "@/services/api"

interface Person {
  id: number
  name: string
  id_card?: string
  watchlist_status?: string
  threat_level?: string
  case?: string
  detection_count?: number
  last_detection?: string
  created_at?: string
}

interface PersonDetailsDialogProps {
  person: Person | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function PersonDetailsDialog({
  person,
  open,
  onOpenChange,
}: PersonDetailsDialogProps) {
  const [details, setDetails] = useState<Person | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (person && open) {
      setLoading(true)
      api.persons
        .getDetails(person.id)
        .then((data) => setDetails(data))
        .catch(() => setDetails(person))
        .finally(() => setLoading(false))
    }
  }, [person, open])

  const getThreatBadgeVariant = (level?: string) => {
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

  const getStatusBadgeVariant = (status?: string) => {
    switch (status?.toLowerCase()) {
      case "watchlist":
        return "destructive"
      case "person of interest":
        return "warning"
      default:
        return "secondary"
    }
  }

  const formatDate = (timestamp?: string) => {
    if (!timestamp) return "N/A"
    return new Date(timestamp).toLocaleString()
  }

  const displayPerson = details || person

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Person Details</DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="space-y-4">
            <Skeleton className="mx-auto h-40 w-40 rounded-lg" />
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        ) : displayPerson ? (
          <div className="space-y-4">
            {/* Photo */}
            <div className="flex justify-center">
              <img
                src={api.persons.getImageUrl(displayPerson.id)}
                alt={displayPerson.name}
                className="h-40 w-40 rounded-lg object-cover border"
              />
            </div>

            {/* Name and Badges */}
            <div className="text-center">
              <h3 className="text-xl font-semibold">{displayPerson.name}</h3>
              <div className="mt-2 flex justify-center gap-2">
                <Badge variant={getStatusBadgeVariant(displayPerson.watchlist_status)}>
                  {displayPerson.watchlist_status || "Normal"}
                </Badge>
                <Badge variant={getThreatBadgeVariant(displayPerson.threat_level)}>
                  {displayPerson.threat_level || "Unknown"} Threat
                </Badge>
              </div>
            </div>

            <Separator />

            {/* Details Grid */}
            <div className="space-y-3">
              {displayPerson.id_card && (
                <div className="flex items-center gap-3">
                  <Hash className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">ID Card</p>
                    <p className="font-medium">{displayPerson.id_card}</p>
                  </div>
                </div>
              )}

              {displayPerson.case && (
                <div className="flex items-start gap-3">
                  <FileText className="mt-0.5 h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">Case Information</p>
                    <p className="font-medium">{displayPerson.case}</p>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3">
                <Eye className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Detection Count</p>
                  <p className="font-medium">{displayPerson.detection_count || 0}</p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Last Detected</p>
                  <p className="font-medium">
                    {displayPerson.last_detection
                      ? formatDate(displayPerson.last_detection)
                      : "Never"}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Enrolled</p>
                  <p className="font-medium">
                    {formatDate(displayPerson.created_at)}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Shield className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-xs text-muted-foreground">Person ID</p>
                  <p className="font-medium">#{displayPerson.id}</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-center text-muted-foreground">No person selected</p>
        )}
      </DialogContent>
    </Dialog>
  )
}
