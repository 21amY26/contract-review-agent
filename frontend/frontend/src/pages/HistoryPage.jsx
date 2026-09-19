import { useState, useEffect } from 'react'
import { fetchHistory } from '@/lib/api'
import Modal from '@/components/ui/Modal'
import { Button } from '@/components/ui/button'
import { useLocalStorage } from '@/hooks/useLocalStorage'

export default function HistoryPage() {
  const [entries, setEntries] = useState([])
  const [selected, setSelected] = useState(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [apiBaseUrl] = useLocalStorage('apiBaseUrl', 'http://localhost:8000')

  useEffect(() => {
    fetchHistory(apiBaseUrl)
      .then(data => setEntries(data))
      .catch(err => console.error(err))
      .finally(() => setLoading(false))
  }, [apiBaseUrl])

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-6">
        <h2 className="text-2xl font-semibold">My analysis history</h2>
        <p className="text-sm text-slate-400">View previously run contract analyses.</p>
      </div>

      <div className="space-y-3">
        {loading ? (
          <div className="text-slate-400">Loading...</div>
        ) : entries.length > 0 ? entries.map((entry, idx) => (
          <div key={idx} className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">{entry.filename || entry.id}</p>
                <p className="font-semibold text-slate-100">{entry.risk_score ? `Risk Score ${entry.risk_score}` : entry.status}</p>
              </div>
              <div className="flex items-center gap-2">
                <div className="text-sm text-slate-400">{new Date(entry.date).toLocaleString()}</div>
                <Button
                  variant="outline"
                  className="px-3 py-1 text-xs"
                  onClick={() => { setSelected(entry); setOpen(true) }}
                >
                  View JSON
                </Button>
              </div>
            </div>
            <div className="mt-3 text-sm text-slate-300 capitalize">Status: {entry.status}</div>
          </div>
        )) : (
          <div className="text-slate-400">No history found.</div>
        )}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title={selected?.filename || selected?.id || 'Entry'}>
        {selected ? (
          <div>
            <p className="text-slate-400">Created at {new Date(selected.date).toLocaleString()}</p>
            <pre className="mt-3 rounded bg-slate-900/80 p-3 text-xs text-slate-300 overflow-auto max-h-96">{JSON.stringify(selected, null, 2)}</pre>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
