import { Navigate, useLocation } from "react-router-dom"
import { Loader2 } from "lucide-react"

import { useAuth } from "@/contexts/AuthContext"

interface ProtectedRouteProps {
  children: React.ReactNode
  requireAdmin?: boolean
}

export function ProtectedRoute({ children, requireAdmin = false }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, isAdmin } = useAuth()
  const location = useLocation()

  // Show loading while checking auth
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Check admin requirement
  if (requireAdmin && !isAdmin) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}
