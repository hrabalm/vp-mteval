import * as React from 'react';
import api from './api';

// adapted from TanStack Router official example

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export interface AuthContext {
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  user: string | null;
  token: string | null;
}


const AuthContext = React.createContext<AuthContext | null>(null)

const userKey = 'vpmteval.auth.user'
const tokenKey = 'vpmteval.auth.token'

function getStoredUser() {
  return localStorage.getItem(userKey)
}

function setStoredUser(user: string | null) {
  if (user) {
    localStorage.setItem(userKey, user)
  } else {
    localStorage.removeItem(userKey)
  }
}

function getStoredToken() {
  return localStorage.getItem(tokenKey)
}

function setStoredToken(token: string | null) {
  if (token) {
    localStorage.setItem(tokenKey, token)
  } else {
    localStorage.removeItem(tokenKey)
  }
}

async function loginPost(username: string, password: string) {
  const res = await api.post('api/login', { username, password })
    .then((r) => r.data)
    .catch((err) => {
      if (err.status === 401) {
        throw new Error('Invalid username or password')
      }
    })
  return res;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<string | null>(getStoredUser())
  const [token, setToken] = React.useState<string | null>(getStoredToken())
  const isAuthenticated = !!user

  const logout = React.useCallback(async () => {
    setStoredUser(null)
    setUser(null)
    setStoredToken(null)
    setToken(null)
  }, [])

  const login = React.useCallback(async (username: string, password: string) => {
    const res = await loginPost(username, password)
    console.log(res)
    setStoredUser(username)
    setUser(username)
    setStoredToken(res.api_key)
    setToken(res.api_key)
  }, [])

  React.useEffect(() => {
    setUser(getStoredUser())
    setToken(getStoredToken())
  }, [])

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = React.useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}