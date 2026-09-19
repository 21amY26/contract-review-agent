import { useEffect, useState } from 'react'
import {
  Settings as SettingsIcon,
  Save,
  CheckCircle2,
  Sun,
  Moon,
  Globe,
  Bell,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useLocalStorage } from '@/hooks/useLocalStorage'

export default function SettingsPage() {
  const [apiBaseUrl, setApiBaseUrl] = useLocalStorage('apiBaseUrl', 'http://localhost:8000')
  const [autosave, setAutosave] = useLocalStorage('autosave', true)
  const [theme, setTheme] = useLocalStorage('theme', 'system')
  const [notifications, setNotifications] = useLocalStorage('notifications', true)
  const [language, setLanguage] = useLocalStorage('language', 'en')
  const [saveMessage, setSaveMessage] = useState('')

  // Preferences persist automatically (via useLocalStorage) the moment they
  // change; this button is an explicit confirmation, not a network save.
  const handleSave = () => {
    setSaveMessage('Preferences saved on this device')
    window.setTimeout(() => setSaveMessage(''), 2200)
  }

  const [userProfile, setUserProfile] = useState(null)

  useEffect(() => {
    const fetchSettings = async () => {
      const token = localStorage.getItem('token')
      if (!token) return
      try {
        const response = await fetch(`${apiBaseUrl}/settings`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (response.ok) {
          const data = await response.json()
          setUserProfile(data)
        }
      } catch (err) {
        console.error('Failed to fetch settings:', err)
      }
    }
    fetchSettings()
  }, [apiBaseUrl])

  // Apply theme to <html> for Tailwind dark mode. "system" follows the OS
  // preference and updates live when the OS theme changes.
  useEffect(() => {
    if (typeof document === 'undefined' || typeof window === 'undefined') return

    const root = document.documentElement
    const media = window.matchMedia('(prefers-color-scheme: dark)')

    const apply = () => {
      const dark = theme === 'dark' || (theme === 'system' && media.matches)
      root.classList.toggle('dark', dark)
    }

    apply()
    if (theme === 'system') {
      media.addEventListener('change', apply)
      return () => media.removeEventListener('change', apply)
    }
  }, [theme])

  const handleReset = () => {
    setApiBaseUrl('http://localhost:8000')
    setAutosave(true)
    setTheme('system')
    setNotifications(true)
    setLanguage('en')
    setSaveMessage('Settings reset to defaults')
    window.setTimeout(() => setSaveMessage(''), 2200)
  }

  return (
    <div className="mx-auto max-w-3xl rounded-3xl border border-slate-800 bg-slate-950/70 p-8 shadow-xl backdrop-blur">
      <div className="mb-6 flex items-center gap-3">
        <div className="rounded-2xl bg-cyan-500/10 p-3 text-cyan-400">
          <SettingsIcon className="h-6 w-6" />
        </div>
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-400">Settings</p>
          <h2 className="text-2xl font-semibold">Workspace configuration</h2>
          {userProfile ? (
            <p className="mt-1 text-sm text-slate-400">Logged in as: {userProfile.email}</p>
          ) : null}
          <p className="mt-1 text-xs text-slate-500">Preferences are stored in this browser and apply instantly.</p>
        </div>
      </div>

      <div className="space-y-5">
        <label className="block text-sm text-slate-300">
          <span className="mb-2 block">API base URL</span>
          <input
            value={apiBaseUrl}
            onChange={(event) => setApiBaseUrl(event.target.value)}
            className="w-full rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-slate-100 outline-none ring-0 focus:border-cyan-400"
            placeholder="https://your-backend.example"
          />
        </label>

        <label className="block text-sm text-slate-300">
          <span className="mb-2 block">Theme</span>
          <div className="flex items-center gap-2">
            <select
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              className="rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-slate-100 outline-none ring-0 focus:border-cyan-400"
            >
              <option value="system">System default</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
            <div className="flex items-center gap-2 text-slate-300">
              {theme === 'dark' ? <Moon className="h-5 w-5 text-cyan-400" /> : <Sun className="h-5 w-5 text-amber-400" />}
            </div>
          </div>
        </label>

        <label className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-sm text-slate-300">
          <span className="flex items-center gap-2"><Bell className="h-4 w-4 text-slate-300" /> Enable notifications</span>
          <input
            type="checkbox"
            checked={notifications}
            onChange={() => setNotifications((v) => !v)}
            className="h-4 w-4 rounded border-slate-700 bg-slate-950 text-cyan-500"
          />
        </label>

        <label className="block text-sm text-slate-300">
          <span className="mb-2 block">Language</span>
          <div className="flex items-center gap-2">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="rounded-2xl border border-slate-700 bg-slate-900 px-4 py-3 text-slate-100 outline-none ring-0 focus:border-cyan-400"
            >
              <option value="en">English</option>
              <option value="es">Español</option>
              <option value="fr">Français</option>
            </select>
            <Globe className="h-5 w-5 text-slate-300" />
          </div>
        </label>

        <label className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-sm text-slate-300">
          <span>Enable automatic review save</span>
          <input
            type="checkbox"
            checked={autosave}
            onChange={() => setAutosave((value) => !value)}
            className="h-4 w-4 rounded border-slate-700 bg-slate-950 text-cyan-500"
          />
        </label>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-2">
            <Button onClick={handleReset} className="bg-slate-800 text-slate-100 hover:bg-slate-700" type="button">
              <RefreshCw className="mr-2 h-4 w-4" />
              Reset defaults
            </Button>
            <Button onClick={handleSave} className="bg-cyan-500 text-slate-950 hover:bg-cyan-400" type="button">
              <Save className="mr-2 h-4 w-4" />
              Save settings
            </Button>
          </div>
          {saveMessage ? (
            <div className="flex items-center gap-2 rounded-2xl bg-slate-900/70 px-4 py-3 text-sm text-slate-200">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              {saveMessage}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
