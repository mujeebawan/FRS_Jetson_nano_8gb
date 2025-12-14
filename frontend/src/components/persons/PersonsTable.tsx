import { useState } from "react"
import { MoreHorizontal, Eye, Trash2, ImagePlus } from "lucide-react"

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

interface Person {
  id: number
  name: string
  id_card?: string
  watchlist_status?: string
  threat_level?: string
  detection_count?: number
  last_detection?: string
}

interface PersonsTableProps {
  persons: Person[]
  onViewDetails: (person: Person) => void
  onAddImage: (person: Person) => void
  onDelete: (person: Person) => void
}

export function PersonsTable({
  persons,
  onViewDetails,
  onAddImage,
  onDelete,
}: PersonsTableProps) {
  const [imageTimestamps, setImageTimestamps] = useState<Record<number, number>>({})

  const getImageUrl = (personId: number) => {
    const timestamp = imageTimestamps[personId] || Date.now()
    return api.persons.getImageUrl(personId, timestamp)
  }

  const handleImageError = (personId: number) => {
    // Update timestamp to force reload
    setImageTimestamps((prev) => ({
      ...prev,
      [personId]: Date.now(),
    }))
  }

  const getStatusBadgeVariant = (status?: string) => {
    switch (status?.toLowerCase()) {
      case "active":
        return "success"
      case "watchlist":
        return "destructive"
      case "person of interest":
        return "warning"
      default:
        return "secondary"
    }
  }

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

  const formatLastSeen = (timestamp?: string) => {
    if (!timestamp) return "Never"
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 60000) return "Just now"
    if (diff < 3600000) return `${Math.floor(diff / 60000)} min ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`
    if (diff < 604800000) return `${Math.floor(diff / 86400000)} days ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">Photo</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>ID Card</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Threat</TableHead>
            <TableHead>Detections</TableHead>
            <TableHead>Last Seen</TableHead>
            <TableHead className="w-12"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {persons.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="h-24 text-center">
                No persons enrolled yet.
              </TableCell>
            </TableRow>
          ) : (
            persons.map((person) => (
              <TableRow
                key={person.id}
                className="cursor-pointer"
                onClick={() => onViewDetails(person)}
              >
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Avatar className="h-10 w-10">
                    <AvatarImage
                      src={getImageUrl(person.id)}
                      alt={person.name}
                      onError={() => handleImageError(person.id)}
                    />
                    <AvatarFallback>
                      {person.name?.charAt(0)?.toUpperCase() || "?"}
                    </AvatarFallback>
                  </Avatar>
                </TableCell>
                <TableCell className="font-medium">{person.name}</TableCell>
                <TableCell className="text-muted-foreground">
                  {person.id_card || "-"}
                </TableCell>
                <TableCell>
                  <Badge variant={getStatusBadgeVariant(person.watchlist_status)}>
                    {person.watchlist_status || "Normal"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={getThreatBadgeVariant(person.threat_level)}>
                    {person.threat_level || "Unknown"}
                  </Badge>
                </TableCell>
                <TableCell>{person.detection_count || 0}</TableCell>
                <TableCell className="text-muted-foreground">
                  {formatLastSeen(person.last_detection)}
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onViewDetails(person)}>
                        <Eye className="mr-2 h-4 w-4" />
                        View Details
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onAddImage(person)}>
                        <ImagePlus className="mr-2 h-4 w-4" />
                        Add Image
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => onDelete(person)}
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
