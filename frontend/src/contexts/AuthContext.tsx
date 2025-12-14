import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"

// Types
export interface User {
  id: number
  username: string
  email: string | null
  role: "admin" | "user"
  is_active: boolean
}

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  isAdmin: boolean
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  refreshAccessToken: () => Promise<boolean>
}

// Context
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// Storage keys
const ACCESS_TOKEN_KEY = "frs_access_token"
const REFRESH_TOKEN_KEY = "frs_refresh_token"
const USER_KEY = "frs_user"

// API base URL (should include /api suffix)
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api"

// Provider
interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: true,
    isAdmin: false,
  })

  // Initialize from localStorage
  useEffect(() => {
    const storedAccessToken = localStorage.getItem(ACCESS_TOKEN_KEY)
    const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
    const storedUser = localStorage.getItem(USER_KEY)

    if (storedAccessToken && storedRefreshToken && storedUser) {
      try {
        const user = JSON.parse(storedUser) as User
        setState({
          user,
          accessToken: storedAccessToken,
          refreshToken: storedRefreshToken,
          isAuthenticated: true,
          isLoading: false,
          isAdmin: user.role === "admin",
        })
      } catch {
        // Invalid stored data, clear it
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
        localStorage.removeItem(USER_KEY)
        setState(prev => ({ ...prev, isLoading: false }))
      }
    } else {
      setState(prev => ({ ...prev, isLoading: false }))
    }
  }, [])

  // Login function
  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || "Login failed")
    }

    const tokens = await response.json()

    // Store tokens
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)

    // Fetch user info
    const userResponse = await fetch(`${API_BASE}/auth/me`, {
      headers: {
        Authorization: `Bearer ${tokens.access_token}`,
      },
    })

    if (!userResponse.ok) {
      throw new Error("Failed to fetch user info")
    }

    const user = await userResponse.json() as User
    localStorage.setItem(USER_KEY, JSON.stringify(user))

    setState({
      user,
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      isAuthenticated: true,
      isLoading: false,
      isAdmin: user.role === "admin",
    })
  }, [])

  // Logout function
  const logout = useCallback(() => {
    // Clear stored data
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem(USER_KEY)

    // Reset state
    setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      isAdmin: false,
    })
  }, [])

  // Refresh access token
  const refreshAccessToken = useCallback(async (): Promise<boolean> => {
    const currentRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)

    if (!currentRefreshToken) {
      logout()
      return false
    }

    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: currentRefreshToken }),
      })

      if (!response.ok) {
        logout()
        return false
      }

      const tokens = await response.json()

      // Update stored tokens
      localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
      localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)

      setState(prev => ({
        ...prev,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      }))

      return true
    } catch {
      logout()
      return false
    }
  }, [logout])

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        logout,
        refreshAccessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// Hook
export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}

// Helper to get current access token (for API calls)
export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}
