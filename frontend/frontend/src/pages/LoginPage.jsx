import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useLocalStorage } from '@/hooks/useLocalStorage'

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [apiBaseUrl] = useLocalStorage('apiBaseUrl', 'http://localhost:8000')

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!email || !password) return
    
    try {
      const formData = new URLSearchParams()
      formData.append('username', email)
      formData.append('password', password)
      
      const response = await fetch(`${apiBaseUrl}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      })
      
      if (!response.ok) {
        throw new Error('Login failed')
      }
      
      const data = await response.json()
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('currentUser', JSON.stringify({ email }))
      navigate('/')
    } catch (err) {
      console.error(err)
      alert(err.message)
    }
  }

  return (
    <div className="max-w-md">
      <h2 className="text-2xl font-semibold">Sign in</h2>
      <p className="mt-2 text-slate-400">Enter your email to continue.</p>
      <form onSubmit={handleLogin} className="mt-6 space-y-4">
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
          <Button type="submit" className="bg-cyan-500 text-slate-950">Sign in</Button>
        </div>
      </form>
    </div>
  )
}
