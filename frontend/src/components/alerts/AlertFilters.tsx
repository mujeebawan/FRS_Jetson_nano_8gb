import { Search } from "lucide-react"

import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface AlertFiltersProps {
  search: string
  onSearchChange: (value: string) => void
  timeRange: string
  onTimeRangeChange: (value: string) => void
  threatLevel: string
  onThreatLevelChange: (value: string) => void
}

export function AlertFilters({
  search,
  onSearchChange,
  timeRange,
  onTimeRangeChange,
  threatLevel,
  onThreatLevelChange,
}: AlertFiltersProps) {
  return (
    <div className="flex flex-wrap gap-4">
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search by person name..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9"
        />
      </div>

      <Select value={timeRange} onValueChange={onTimeRangeChange}>
        <SelectTrigger className="w-[150px]">
          <SelectValue placeholder="Time Range" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="24h">Last 24 Hours</SelectItem>
          <SelectItem value="7d">Last 7 Days</SelectItem>
          <SelectItem value="30d">Last 30 Days</SelectItem>
          <SelectItem value="all">All Time</SelectItem>
        </SelectContent>
      </Select>

      <Select value={threatLevel} onValueChange={onThreatLevelChange}>
        <SelectTrigger className="w-[150px]">
          <SelectValue placeholder="Threat Level" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Levels</SelectItem>
          <SelectItem value="high">High</SelectItem>
          <SelectItem value="medium">Medium</SelectItem>
          <SelectItem value="low">Low</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}
