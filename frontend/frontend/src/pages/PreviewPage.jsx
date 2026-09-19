import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, ShieldAlert, FileText, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'

function riskTone(risk) {
  const r = String(risk || '').toLowerCase()
  if (r === 'high') return 'bg-rose-500/15 text-rose-300'
  if (r === 'low') return 'bg-emerald-500/15 text-emerald-300'
  if (r === 'n/a') return 'bg-slate-700/40 text-slate-300'
  return 'bg-amber-500/15 text-amber-300'
}

export default function PreviewPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const results = location.state?.results
  const query = useMemo(() => new URLSearchParams(location.search), [location.search])

  const contractData = useMemo(() => {
    if (!results) return null
    const meta = results.raw?.contract_metadata || {}
    const clauses =
      results.findings?.map((f, i) => ({
        id: `clause-${i}`,
        title: f.clause,
        risk: f.risk,
        summary: f.summary,
      })) || []

    return {
      name: meta.contract_type || 'Analyzed contract',
      parties: (meta.parties || []).join(' and ') || 'N/A',
      date: meta.effective_date || 'N/A',
      summary: results.raw?.document_summary || 'Review complete.',
      clauses:
        clauses.length > 0
          ? clauses
          : [{ id: 'none', title: 'No issues found', risk: 'Low', summary: 'No significant issues were flagged.' }],
    }
  }, [results])

  const defaultClauseId = contractData?.clauses[0]?.id
  const [selectedClauseId, setSelectedClauseId] = useState(query.get('clause') || defaultClauseId)

  const selectedClause = useMemo(() => {
    if (!contractData) return null
    return contractData.clauses.find((item) => item.id === selectedClauseId) ?? contractData.clauses[0]
  }, [selectedClauseId, contractData])

  // ---- Empty state (no analysis was passed to this page) ----
  if (!contractData) {
    return (
      <div className="mx-auto max-w-xl">
        <div className="flex flex-col items-center gap-5 rounded-3xl border border-slate-800 bg-slate-950/70 p-10 text-center shadow-xl backdrop-blur">
          <div className="rounded-2xl bg-cyan-500/10 p-4 text-cyan-300">
            <FileText className="h-8 w-8" />
          </div>
          <div>
            <h2 className="text-2xl font-semibold">No contract loaded</h2>
            <p className="mt-2 text-slate-400">
              Run an analysis first, then open the preview to inspect clauses and risk detail.
            </p>
          </div>
          <Button
            onClick={() => navigate('/analysis')}
            className="bg-cyan-500 text-slate-950 hover:bg-cyan-400"
          >
            <Sparkles className="mr-2 h-4 w-4" />
            Go to analysis
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-8 shadow-xl backdrop-blur">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-400">Contract preview</p>
            <h2 className="mt-2 text-3xl font-semibold">Clause detail and contract summary</h2>
            <p className="mt-2 text-slate-400">Inspect highlighted clauses and drill into risk detail.</p>
          </div>
          <Button onClick={() => navigate('/analysis')} className="bg-slate-700 text-slate-100 hover:bg-slate-600">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to analysis
          </Button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_0.7fr]">
        <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-xl">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm text-slate-400">Contract</p>
              <h3 className="mt-2 text-2xl font-semibold text-slate-100">{contractData.name}</h3>
            </div>
            <div className="space-y-2 text-sm text-slate-300">
              <div>
                <span className="font-semibold text-slate-100">Parties:</span> {contractData.parties}
              </div>
              <div>
                <span className="font-semibold text-slate-100">Date:</span> {contractData.date}
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 text-slate-300">
            <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Contract summary</p>
            <p className="mt-4 leading-7 text-slate-200">{contractData.summary}</p>
          </div>
        </section>

        <aside className="space-y-6">
          <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-xl">
            <div className="mb-4 flex items-center gap-3 text-cyan-300">
              <Eye className="h-5 w-5" />
              <h3 className="text-xl font-semibold">Clause highlights</h3>
            </div>
            <div className="space-y-3">
              {contractData.clauses.map((clause) => (
                <button
                  key={clause.id}
                  type="button"
                  onClick={() => setSelectedClauseId(clause.id)}
                  className={`w-full rounded-3xl border px-4 py-4 text-left transition ${
                    selectedClause?.id === clause.id
                      ? 'border-cyan-500 bg-slate-900 text-slate-100 shadow-lg shadow-cyan-500/10'
                      : 'border-slate-800 bg-slate-900/70 text-slate-300 hover:border-slate-600 hover:bg-slate-900'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-100">{clause.title}</p>
                    <span className={`rounded-full px-3 py-1 text-xs font-medium ${riskTone(clause.risk)}`}>
                      {clause.risk}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-slate-400">{clause.summary}</p>
                </button>
              ))}
            </div>
          </div>

          {selectedClause && (
            <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-xl">
              <div className="mb-4 flex items-center gap-3 text-amber-300">
                <ShieldAlert className="h-5 w-5" />
                <h3 className="text-xl font-semibold">Selected clause detail</h3>
              </div>
              <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5 text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm uppercase tracking-[0.3em] text-slate-500">{selectedClause.title}</p>
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${riskTone(selectedClause.risk)}`}>
                    {selectedClause.risk}
                  </span>
                </div>
                <p className="mt-3 leading-7 text-slate-200">{selectedClause.summary}</p>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
