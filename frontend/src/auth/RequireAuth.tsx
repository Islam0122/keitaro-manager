import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { PageLoader } from '@/components/ui/Spinner'

import { useAuth } from './AuthContext'

export function RequireAuth() {
  const { user, initializing } = useAuth()
  const location = useLocation()
  if (initializing) return <PageLoader label="Проверка сессии…" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}
