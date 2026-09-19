import { useMemo, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileUp, ShieldAlert, Sparkles, Download, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { UploadZone } from '@/components/UploadZone'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import { startAnalysis, checkAnalysisStatus, generateReportBlob, mapAnalysisResponse } from '@/lib/api'

export default function AnalysisPage() {
  const navigate = useNavigate()
  const [selectedFile, setSelectedFile] = useState(null)
  const [candidate, setCandidate] = useState('')
  const [status, setStatus] = useState('Ready to review a contract')
  const [results, setResults] = useState(null)
  const [apiBaseUrl] = useLocalStorage('apiBaseUrl', 'http://localhost:8000')
  const [isPolling, setIsPolling] = useState(false)
  const [contractId, setContractId] = useState(null)

  const summary = useMemo(
    () => [
      { label: 'Overall risk', value: results ? `${results.overallRisk}%` : '—', tone: 'text-amber-300' },
      { label: 'High-risk clauses', value: results ? results.highRisk : '—', tone: 'text-rose-300' },
      { label: 'Compliance gaps', value: results ? results.gaps : '—', tone: 'text-cyan-300' },
    ],
    [results],
  )

  const [preview, setPreview] = useState(null)
  const closePreview = () => setPreview(null)

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setStatus('Choose a contract file to start the review')
      return
    }

    setStatus(`Uploading ${selectedFile.name}...`)
    setResults(null)
    setIsPolling(true)

    try {
      const response = await startAnalysis(selectedFile, apiBaseUrl)
      setContractId(response.contract_id)
      setStatus('Analysis pending...')
    } catch (error) {
      console.error(error)
      setStatus('Unable to reach backend or start analysis.')
      setIsPolling(false)
    }
  }

  useEffect(() => {
    let intervalId;
    if (isPolling && contractId) {
      intervalId = setInterval(async () => {
        try {
          const res = await checkAnalysisStatus(contractId, apiBaseUrl)
          if (res.status === 'completed' || res.status === 'completed_with_errors') {
            clearInterval(intervalId)
            setIsPolling(false)
            
            const mapped = mapAnalysisResponse(res)
            setResults({
              ...mapped,
              reportLink: `${selectedFile?.name?.replace(/\.[^/.]+$/, '') || 'report'}-review.pdf`,
            })
            setStatus(`Review complete for ${selectedFile?.name}`)
          } else if (res.status === 'rejected') {
            clearInterval(intervalId)
            setIsPolling(false)
            setStatus(
              res.intake_notes
                ? `This document doesn't appear to be a contract. ${res.intake_notes}`
                : "This document doesn't appear to be a contract.",
            )
          } else if (res.status === 'failed') {
            clearInterval(intervalId)
            setIsPolling(false)
            setStatus('Analysis failed.')
          } else {
            const steps = res.completed_steps || []
            const lastStep = steps[steps.length - 1] || 'Processing...'
            setStatus(`Status: ${res.status}. ${lastStep.replace(/_/g, ' ')}`)
          }
        } catch (err) {
          console.error('Polling error:', err)
          clearInterval(intervalId)
          setIsPolling(false)
          setStatus('Lost connection during analysis.')
        }
      }, 3000)
    }
    return () => clearInterval(intervalId)
  }, [isPolling, contractId, apiBaseUrl, selectedFile])

  const handleDownload = () => {
    if (!results) return
    const blob = generateReportBlob(results, { candidate, fileName: selectedFile?.name })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${(selectedFile?.name || 'report').replace(/\.[^/.]+$/, '')}-review.txt`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-8 shadow-xl backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-cyan-400">Analysis workspace</p>
            <h2 className="mt-2 text-3xl font-semibold">Contract review dashboard</h2>
            <p className="mt-2 text-slate-400">Upload your contract and get an agentic review summary with RAG-enhanced clause analysis and compliance risk guidance.</p>
          </div>
          <Button
            disabled={!results}
            onClick={handleDownload}
            className="bg-cyan-500 text-slate-950 hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-slate-700"
          >
            <Download className="mr-2 h-4 w-4" />
            {results ? 'Download report' : 'Generate report after analysis'}
          </Button>
        </div>
      {preview && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-xl rounded-2xl bg-slate-950 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">{preview.clause}</h3>
              <button onClick={closePreview} className="text-sm text-slate-400">Close</button>
            </div>
            <p className="mt-4 text-sm text-slate-300">{preview.text}</p>
          </div>
        </div>
      )}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {summary.map((item) => (
          <div key={item.label} className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
            <p className="text-sm text-slate-400">{item.label}</p>
            <p className={`mt-2 text-3xl font-semibold ${item.tone}`}>{item.value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-xl">
          <div className="mb-4 flex items-center gap-2 text-cyan-300">
            <FileUp className="h-5 w-5" />
            <h3 className="text-xl font-semibold">Upload contract</h3>
          </div>
          <UploadZone selectedFile={selectedFile} onFileSelect={setSelectedFile} />

          <div className="mt-4">
            <label className="text-sm text-slate-400">Candidate name (optional)</label>
            <input
              value={candidate}
              onChange={(e) => setCandidate(e.target.value)}
              placeholder="e.g. John Doe"
              className="mt-2 w-full rounded-2xl border border-slate-700 bg-slate-900/80 py-2 px-3 text-slate-100 outline-none"
            />
          </div>

          <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-300">
            <p className="font-medium text-slate-200 flex items-center gap-2">
              Status 
              {isPolling && <Loader2 className="h-4 w-4 animate-spin text-cyan-500" />}
            </p>
            <p className="mt-1 capitalize">{status}</p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button disabled={isPolling} onClick={handleAnalyze} className="mt-4 bg-cyan-500 text-slate-950 hover:bg-cyan-400 disabled:bg-slate-700">
              <Sparkles className="mr-2 h-4 w-4" />
              {isPolling ? 'Analyzing...' : 'Analyze contract'}
            </Button>
            <Button
              onClick={() => navigate('/preview', { state: { results } })}
              className="mt-4 bg-slate-700 text-slate-100 hover:bg-slate-600"
              variant="outline"
              disabled={!results}
            >
              <FileUp className="mr-2 h-4 w-4" />
              View contract preview
            </Button>
          </div>
        </div>

        <div className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-xl">
          <div className="mb-4 flex items-center gap-2 text-amber-300">
            <ShieldAlert className="h-5 w-5" />
            <h3 className="text-xl font-semibold">Risk findings</h3>
          </div>

          <div className="space-y-3">
            {results?.findings ? results.findings.map((item, idx) => (
              <div key={idx} className="w-full rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-left transition hover:border-cyan-500 hover:bg-slate-900">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold text-slate-100">{item.clause}</p>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-amber-500/15 px-2.5 py-1 text-xs font-medium text-amber-300">{item.risk}</span>
                    <Button
                      variant="outline"
                      className="text-xs"
                      onClick={() => setPreview({ clause: item.clause, text: item.summary })}
                    >
                      View
                    </Button>
                  </div>
                </div>
                <p className="mt-2 text-sm text-slate-400">{item.summary}</p>
              </div>
            )) : (
              <p className="text-sm text-slate-400 mt-4">Upload and analyze a contract to view findings.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
