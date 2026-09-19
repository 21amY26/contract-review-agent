import { useEffect, useMemo, useState } from 'react'
import {
  Search,
  Download,
  FileText,
  PieChart,
  ShieldAlert,
  Loader2,
  Inbox,
} from 'lucide-react'
import Modal from '@/components/ui/Modal'
import { Button } from '@/components/ui/button'
import { fetchReports } from '@/lib/api'
import { useLocalStorage } from '@/hooks/useLocalStorage'

// ---------------------------------------------------------------------------
// Presentation helpers — the /reports API returns:
//   { id, filename, date, status, risk_score }   (risk_score is 0–100)
// ---------------------------------------------------------------------------

function riskBucket(score) {
  const n = Number(score) || 0
  if (n >= 60) return { label: 'High', tone: 'rose', bar: 'bg-rose-400', text: 'text-rose-300' }
  if (n >= 30) return { label: 'Medium', tone: 'amber', bar: 'bg-amber-400', text: 'text-amber-300' }
  return { label: 'Low', tone: 'emerald', bar: 'bg-emerald-400', text: 'text-emerald-300' }
}

function statusLabel(status) {
  switch (status) {
    case 'completed':
      return { text: 'Complete', className: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20' }
    case 'completed_with_errors':
      return { text: 'Completed · warnings', className: 'bg-amber-500/10 text-amber-300 border-amber-500/20' }
    case 'rejected':
      return { text: 'Rejected', className: 'bg-slate-700/40 text-slate-300 border-slate-600/40' }
    case 'failed':
      return { text: 'Failed', className: 'bg-rose-500/10 text-rose-300 border-rose-500/20' }
    default:
      return { text: status || 'Unknown', className: 'bg-slate-700/40 text-slate-300 border-slate-600/40' }
  }
}

function formatDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  return Number.isNaN(d.getTime())
    ? String(value)
    : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function downloadReport(report) {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${report.filename?.replace(/\.[^/.]+$/, '') || report.id || 'report'}.json`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default function ReportsPage() {
  const [query, setQuery] = useState('')
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedReport, setSelectedReport] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)

  const [apiBaseUrl] = useLocalStorage('apiBaseUrl', 'http://localhost:8000')

  useEffect(() => {
    let active = true
    setLoading(true)
    fetchReports(apiBaseUrl)
      .then((data) => {
        if (!active) return
        setReports(Array.isArray(data) ? data : [])
        setError(null)
      })
      .catch((err) => {
        if (!active) return
        console.error(err)
        setReports([])
        setError('Could not load reports. Check that you are signed in and the backend is reachable.')
      })
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [apiBaseUrl])

  const filteredReports = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return reports
    return reports.filter((report) =>
      [report.filename, report.id, report.status]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(q)),
    )
  }, [query, reports])

  const stats = useMemo(() => {
    if (reports.length === 0) return { total: 0, avg: 0, high: 0 }
    const scores = reports.map((r) => Number(r.risk_score) || 0)
    const avg = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
    const high = scores.filter((s) => s >= 60).length
    return { total: reports.length, avg, high }
  }, [reports])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-8 shadow-xl backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-400">Reports</p>
            <h2 className="mt-2 text-3xl font-semibold">Saved contract review reports</h2>
            <p className="mt-2 max-w-2xl text-slate-400">
              Revisit completed reviews, search your history, and export summaries for your audit trail.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[0.82fr_0.58fr]">
        {/* Report list */}
        <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-xl">
          <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-xl font-semibold">Report history</h3>
              <p className="text-sm text-slate-400">Search and revisit previously generated reviews.</p>
            </div>
            <div className="relative w-full sm:max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by file, id, or status"
                className="w-full rounded-2xl border border-slate-700 bg-slate-900/80 py-2.5 pl-10 pr-4 text-slate-100 outline-none transition focus:border-cyan-400"
              />
            </div>
          </div>

          <div className="space-y-3">
            {loading ? (
              <div className="flex items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 text-slate-400">
                <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
                Loading reports…
              </div>
            ) : error ? (
              <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-6 text-sm text-rose-200">
                {error}
              </div>
            ) : filteredReports.length === 0 ? (
              <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-slate-700 bg-slate-900/50 p-10 text-center text-slate-400">
                <Inbox className="h-8 w-8 text-slate-500" />
                <p className="font-medium text-slate-300">
                  {reports.length === 0 ? 'No reports yet' : 'No matching reports'}
                </p>
                <p className="text-sm">
                  {reports.length === 0
                    ? 'Run an analysis to see completed reviews here.'
                    : 'Try a different search term.'}
                </p>
              </div>
            ) : (
              filteredReports.map((report) => {
                const risk = riskBucket(report.risk_score)
                const status = statusLabel(report.status)
                const score = Math.round(Number(report.risk_score) || 0)
                return (
                  <div
                    key={report.id}
                    className="group rounded-2xl border border-slate-800 bg-slate-900/70 p-5 transition hover:border-cyan-500/40 hover:bg-slate-900"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="flex items-start gap-3">
                        <div className="rounded-xl bg-cyan-500/10 p-2.5 text-cyan-300">
                          <FileText className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                          <h4 className="truncate text-base font-semibold text-slate-100">
                            {report.filename || report.id}
                          </h4>
                          <p className="mt-0.5 text-xs text-slate-500">
                            {report.id} · {formatDate(report.date)}
                          </p>
                        </div>
                      </div>
                      <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium ${status.className}`}>
                        {status.text}
                      </span>
                    </div>

                    <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
                      <div className="flex min-w-[180px] flex-1 items-center gap-3">
                        <div className="h-2 w-full max-w-[160px] overflow-hidden rounded-full bg-slate-800">
                          <div
                            className={`h-2 rounded-full ${risk.bar}`}
                            style={{ width: `${Math.min(100, Math.max(4, score))}%` }}
                          />
                        </div>
                        <span className={`text-sm font-semibold ${risk.text}`}>
                          {score}% · {risk.label}
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          className="rounded-full border-slate-700 px-3 py-2 text-xs text-slate-200"
                          onClick={() => {
                            setSelectedReport(report)
                            setModalOpen(true)
                          }}
                        >
                          View
                        </Button>
                        <Button
                          className="rounded-full bg-cyan-500 px-3 py-2 text-xs text-slate-950 hover:bg-cyan-400"
                          onClick={() => downloadReport(report)}
                        >
                          <Download className="mr-1 h-3.5 w-3.5" />
                          Export
                        </Button>
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Portfolio snapshot — computed from real data */}
        <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-xl">
          <div className="flex items-center gap-3 text-cyan-300">
            <PieChart className="h-5 w-5" />
            <h3 className="text-xl font-semibold">Portfolio snapshot</h3>
          </div>
          <div className="mt-6 space-y-4 text-sm text-slate-300">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
              <p className="text-slate-400">Completed reviews</p>
              <p className="mt-2 text-3xl font-semibold text-slate-100">{stats.total}</p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
              <p className="text-slate-400">Average risk score</p>
              <p className={`mt-2 text-3xl font-semibold ${riskBucket(stats.avg).text}`}>
                {stats.total ? `${stats.avg}%` : '—'}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-4">
              <div className="flex items-center justify-between">
                <p className="text-slate-400">High-risk reviews</p>
                <ShieldAlert className="h-4 w-4 text-rose-300" />
              </div>
              <p className="mt-2 text-3xl font-semibold text-rose-300">{stats.high}</p>
            </div>
          </div>
        </div>
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={selectedReport?.filename || selectedReport?.id || 'Report'}
      >
        {selectedReport ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-xs text-slate-500">Report ID</p>
                <p className="mt-1 font-medium text-slate-200">{selectedReport.id}</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-xs text-slate-500">Date</p>
                <p className="mt-1 font-medium text-slate-200">{formatDate(selectedReport.date)}</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-xs text-slate-500">Status</p>
                <p className="mt-1 font-medium text-slate-200">{statusLabel(selectedReport.status).text}</p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-xs text-slate-500">Risk score</p>
                <p className={`mt-1 font-semibold ${riskBucket(selectedReport.risk_score).text}`}>
                  {Math.round(Number(selectedReport.risk_score) || 0)}% · {riskBucket(selectedReport.risk_score).label}
                </p>
              </div>
            </div>
            <div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-2.5 rounded-full ${riskBucket(selectedReport.risk_score).bar}`}
                  style={{
                    width: `${Math.min(100, Math.max(4, Math.round(Number(selectedReport.risk_score) || 0)))}%`,
                  }}
                />
              </div>
            </div>
            <div className="flex justify-end">
              <Button
                className="rounded-full bg-cyan-500 px-4 py-2 text-xs text-slate-950 hover:bg-cyan-400"
                onClick={() => downloadReport(selectedReport)}
              >
                <Download className="mr-1 h-3.5 w-3.5" />
                Export JSON
              </Button>
            </div>
          </div>
        ) : (
          <div>No report selected.</div>
        )}
      </Modal>
    </div>
  )
}
