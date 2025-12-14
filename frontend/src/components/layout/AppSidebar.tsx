import { NavLink, useLocation } from "react-router-dom"
import {
  LayoutDashboard,
  Users,
  Bell,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
  Activity,
  Camera,
} from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Badge } from "@/components/ui/badge"

interface AppSidebarProps {
  collapsed: boolean
  onToggle: () => void
  alertCount?: number
  streamStatus?: "active" | "inactive" | "error"
  cameraStatus?: "connected" | "disconnected" | "error"
}

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Persons", href: "/persons", icon: Users },
  { name: "Alerts", href: "/alerts", icon: Bell },
  { name: "Settings", href: "/settings", icon: Settings },
]

export function AppSidebar({
  collapsed,
  onToggle,
  alertCount = 0,
  streamStatus = "inactive",
  cameraStatus = "disconnected",
}: AppSidebarProps) {
  const location = useLocation()

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
      case "connected":
        return "bg-green-500"
      case "inactive":
      case "disconnected":
        return "bg-gray-400"
      case "error":
        return "bg-red-500"
      default:
        return "bg-gray-400"
    }
  }

  return (
    <aside
      className={cn(
        "flex flex-col border-r bg-sidebar transition-all duration-300 ease-in-out",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Header */}
      <div className="flex h-16 items-center justify-between border-b px-4">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-primary" />
            <span className="font-semibold text-sidebar-foreground">
              FRS Security
            </span>
          </div>
        )}
        {collapsed && <Shield className="h-6 w-6 text-primary mx-auto" />}
        <Button
          variant="ghost"
          size="icon"
          className={cn("h-8 w-8", collapsed && "mx-auto mt-2")}
          onClick={onToggle}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 py-4">
        <nav className="space-y-1 px-2">
          {navigation.map((item) => {
            const isActive = location.pathname.startsWith(item.href)
            const Icon = item.icon
            const showBadge = item.name === "Alerts" && alertCount > 0

            const linkContent = (
              <NavLink
                to={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  collapsed && "justify-center px-2"
                )}
              >
                <Icon className="h-5 w-5 shrink-0" />
                {!collapsed && (
                  <>
                    <span className="flex-1">{item.name}</span>
                    {showBadge && (
                      <Badge
                        variant="destructive"
                        className="h-5 min-w-5 px-1.5 text-xs"
                      >
                        {alertCount > 99 ? "99+" : alertCount}
                      </Badge>
                    )}
                  </>
                )}
                {collapsed && showBadge && (
                  <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] text-destructive-foreground">
                    {alertCount > 9 ? "9+" : alertCount}
                  </span>
                )}
              </NavLink>
            )

            if (collapsed) {
              return (
                <Tooltip key={item.name} delayDuration={0}>
                  <TooltipTrigger asChild>
                    <div className="relative">{linkContent}</div>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="flex items-center gap-2">
                    {item.name}
                    {showBadge && (
                      <Badge variant="destructive" className="h-5 px-1.5 text-xs">
                        {alertCount}
                      </Badge>
                    )}
                  </TooltipContent>
                </Tooltip>
              )
            }

            return <div key={item.name}>{linkContent}</div>
          })}
        </nav>
      </ScrollArea>

      {/* Footer with Status */}
      <div className="border-t p-3">
        {!collapsed ? (
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between text-sidebar-foreground">
              <span className="flex items-center gap-2">
                <Activity className="h-3.5 w-3.5" />
                Stream
              </span>
              <span className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    getStatusColor(streamStatus)
                  )}
                />
                <span className="capitalize">{streamStatus}</span>
              </span>
            </div>
            <div className="flex items-center justify-between text-sidebar-foreground">
              <span className="flex items-center gap-2">
                <Camera className="h-3.5 w-3.5" />
                Camera
              </span>
              <span className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    getStatusColor(cameraStatus)
                  )}
                />
                <span className="capitalize">{cameraStatus}</span>
              </span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-1">
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      getStatusColor(streamStatus)
                    )}
                  />
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      getStatusColor(cameraStatus)
                    )}
                  />
                </div>
              </TooltipTrigger>
              <TooltipContent side="right">
                <div className="space-y-1 text-xs">
                  <div>Stream: {streamStatus}</div>
                  <div>Camera: {cameraStatus}</div>
                </div>
              </TooltipContent>
            </Tooltip>
          </div>
        )}
      </div>
    </aside>
  )
}
