import { useLocation } from "react-router-dom"
import { ChevronRight } from "lucide-react"

import { ThemeToggle } from "./ThemeToggle"

const pageTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/persons": "Persons",
  "/alerts": "Alerts",
  "/settings": "Settings",
}

export function Header() {
  const location = useLocation()

  // Get the base path for matching
  const basePath = "/" + location.pathname.split("/")[1]
  const pageTitle = pageTitles[basePath] || "Dashboard"

  return (
    <header className="flex h-16 items-center justify-between border-b bg-background px-6">
      <nav className="flex items-center space-x-1 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">FRS</span>
        <ChevronRight className="h-4 w-4" />
        <span className="text-foreground">{pageTitle}</span>
      </nav>
      <ThemeToggle />
    </header>
  )
}
