import { MoreHorizontal, Eye, Check, Trash2, Video } from "lucide-react"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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
  similarity?: number
}

interface AlertsTableProps {
  alerts: Alert[]
  onViewDetails: (alert: Alert) => void
  onAcknowledge: (alert: Alert) => void
  onVerify: (alert: Alert) => void
  onDelete: (alert: Alert) => void
}

export function AlertsTable({
  alerts,
  onViewDetails,
  onAcknowledge,
  onVerify,
  onDelete,
}: AlertsTableProps) {
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

  const getStatusBadge = (alert: Alert) => {
    if (alert.verified) {
      return (
        <Badge variant="outline" className="border-green-500 text-green-500">
          Verified
        </Badge>
      )
    }
    if (alert.acknowledged) {
      return <Badge variant="secondary">Acknowledged</Badge>
    }
    return <Badge variant="default">New</Badge>
  }

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleString()
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">Snapshot</TableHead>
            <TableHead>Person</TableHead>
            <TableHead>Threat</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>Time</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-12"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {alerts.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="h-24 text-center">
                No alerts found.
              </TableCell>
            </TableRow>
          ) : (
            alerts.map((alert) => (
              <TableRow
                key={alert.id}
                className={`cursor-pointer ${
                  !alert.acknowledged ? "bg-muted/30" : ""
                }`}
                onClick={() => onViewDetails(alert)}
              >
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Avatar className="h-12 w-12 rounded-md">
                    <AvatarImage
                      src={api.alerts.getSnapshotUrl(alert.id)}
                      alt="Alert snapshot"
                      className="object-cover"
                    />
                    <AvatarFallback className="rounded-md">?</AvatarFallback>
                  </Avatar>
                </TableCell>
                <TableCell className="font-medium">
                  {alert.person_name || "Unknown Person"}
                </TableCell>
                <TableCell>
                  <Badge variant={getThreatBadgeVariant(alert.threat_level)}>
                    {alert.threat_level || "Unknown"}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {alert.similarity
                    ? `${(alert.similarity * 100).toFixed(0)}%`
                    : "-"}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {formatTime(alert.timestamp)}
                </TableCell>
                <TableCell>{getStatusBadge(alert)}</TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onViewDetails(alert)}>
                        <Eye className="mr-2 h-4 w-4" />
                        View Details
                      </DropdownMenuItem>
                      {!alert.acknowledged && (
                        <DropdownMenuItem onClick={() => onAcknowledge(alert)}>
                          <Check className="mr-2 h-4 w-4" />
                          Acknowledge
                        </DropdownMenuItem>
                      )}
                      {!alert.verified && (
                        <DropdownMenuItem onClick={() => onVerify(alert)}>
                          <Video className="mr-2 h-4 w-4" />
                          Verify
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => onDelete(alert)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  )
}
