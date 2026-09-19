import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useLocalStorage } from '@/hooks/useLocalStorage'

export default function SignupPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [apiBaseUrl] = useLocalStorage('apiBaseUrl', 'http://localhost:8000')

  const handleSignup = async (e) => {
    e.preventDefault()
    if (!email || !password) return
    
    try {
      const response = await fetch(`${apiBaseUrl}/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Signup failed' }))
        throw new Error(err.detail || 'Signup failed')
      }
      
      // Auto-login after successful signup
      const loginResp = await fetch(`${apiBaseUrl}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }),
      })
      if (!loginResp.ok) {
        throw new Error('Auto-login failed')
      }
      const loginData = await loginResp.json()
      localStorage.setItem('token', loginData.access_token)
      localStorage.setItem('currentUser', JSON.stringify({ email }))
      navigate('/')
    } catch (err) {
      console.error(err)
      alert(err.message)
    }
  }

  return (
    <div className="max-w-md">
      <h2 className="text-2xl font-semibold">Create an account</h2>
      <p className="mt-2 text-slate-400">Sign up to save candidate history and reports.</p>
      <form onSubmit={handleSignup} className="mt-6 space-y-4">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="w-full rounded-2xl border border-slate-700 bg-slate-900/80 py-2 px-3 text-slate-100 outline-none"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="w-full rounded-2xl border border-slate-700 bg-slate-900/80 py-2 px-3 text-slate-100 outline-none"
        />
        <div>
          <Button type="submit" className="bg-cyan-500 text-slate-950">Create account</Button>
        </div>
      </form>
    </div>
  )
}
