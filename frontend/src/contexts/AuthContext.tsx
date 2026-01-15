import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

interface User {
  id: number;
  username: string;
  role: 'admin' | 'user';
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing token on mount
  useEffect(() => {
    const storedToken = localStorage.getItem('frs_access_token');
    if (storedToken) {
      setToken(storedToken);
      // Validate token by fetching user info
      validateToken(storedToken);
    } else {
      setIsLoading(false);
    }
  }, []);

  const validateToken = async (accessToken: string) => {
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || 'http://192.168.0.245:8000/api'}/auth/me`,
        {
          headers: { Authorization: `Bearer ${accessToken}` },
        }
      );
      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
        setToken(accessToken);
      } else {
        // Token invalid, clear it
        localStorage.removeItem('frs_access_token');
        localStorage.removeItem('frs_refresh_token');
        setToken(null);
        setUser(null);
      }
    } catch (error) {
      console.error('Token validation failed:', error);
      localStorage.removeItem('frs_access_token');
      localStorage.removeItem('frs_refresh_token');
      setToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (username: string, password: string) => {
    const response = await fetch(
      `${import.meta.env.VITE_API_URL || 'http://192.168.0.245:8000/api'}/auth/login`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();

    // Store tokens
    localStorage.setItem('frs_access_token', data.access_token);
    if (data.refresh_token) {
      localStorage.setItem('frs_refresh_token', data.refresh_token);
    }

    setToken(data.access_token);

    // Fetch user info
    await validateToken(data.access_token);
  };

  const logout = () => {
    localStorage.removeItem('frs_access_token');
    localStorage.removeItem('frs_refresh_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
