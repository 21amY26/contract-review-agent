import { Navigate, useLocation } from 'react-router-dom'

/**
 * Route guard: renders children only when a JWT is present in localStorage.
 * Otherwise redirects to /login, preserving the attempted location so the
 * login flow could send the user back later.
 */
export default function RequireAuth({ children }) {
  const location = useLocation()
  const token = localStorage.getItem('token')

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}
