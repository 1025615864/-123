import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import api from '../api/client'
import type { User } from '../types'

interface AuthContextType {
  user: User | null
  token: string | null
  login: (username: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))

  const logout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  useEffect(() => {
    const handler = () => logout()
    window.addEventListener('auth:logout', handler)
    return () => window.removeEventListener('auth:logout', handler)
  }, [])

  useEffect(() => {
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      fetchUser(token)
    } else {
      delete api.defaults.headers.common['Authorization']
    }
  }, [token])

  const fetchUser = async (activeToken: string) => {
    try {
      const response = await api.get('/user/me', {
        headers: {
          Authorization: `Bearer ${activeToken}`,
        },
      })
      if (localStorage.getItem('token') !== activeToken) {
        return
      }
      setUser(response.data)
    } catch {
      if (localStorage.getItem('token') === activeToken) {
        logout()
      }
    }
  }

  const login = async (username: string, password: string) => {
    const response = await api.post('/user/login', { username, password })
    
    const { token, user: userData } = response.data
    localStorage.setItem('token', token.access_token)
    setToken(token.access_token)
    setUser(userData)
  }

  const register = async (username: string, email: string, password: string) => {
    await api.post('/user/register', { username, email, password })
  }

  return (
    <AuthContext.Provider value={{
      user,
      token,
      login,
      register,
      logout,
      isAuthenticated: !!token
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
