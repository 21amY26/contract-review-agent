import { ArrowRight, ShieldCheck, Sparkles } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'

const highlights = [
  'Multi-agent orchestration for review workflows',
  'RAG-powered clause extraction and context retrieval',
  'Compliance risk scoring and audit-ready outputs',
]

export default function HomePage() {
  const navigate = useNavigate()

  return (
    <section className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
      <div className="space-y-6 rounded-3xl border border-slate-800 bg-slate-950/70 p-8 shadow-2xl shadow-cyan-950/20 backdrop-blur sm:p-10">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-sm text-cyan-300">
          <Sparkles className="h-4 w-4" />
          AI-assisted contract compliance
        </div>

        <div className="space-y-4">
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
            Agentic contract review with RAG, LLMs, and risk orchestration.
          </h1>
          <p className="max-w-2xl text-lg text-slate-300">
            Upload a contract, inspect risky clauses, and generate compliance-ready review summaries through a multi-agent workflow.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button onClick={() => navigate('/analysis')} className="bg-cyan-500 text-slate-950 hover:bg-cyan-400">
            Open dashboard
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
          <Button variant="outline" onClick={() => navigate('/settings')}>
            Configure backend
          </Button>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-8 shadow-xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="rounded-2xl bg-cyan-500/10 p-3 text-cyan-400">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <p className="text-lg font-semibold">Built for legal and compliance teams</p>
            <p className="text-sm text-slate-400">From intake to review-ready reporting</p>
          </div>
        </div>

        <ul className="space-y-4 text-sm text-slate-300">
          {highlights.map((item) => (
            <li key={item} className="flex items-start gap-2">
              <span className="mt-1.5 h-2 w-2 rounded-full bg-cyan-400" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
