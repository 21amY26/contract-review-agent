const defaultApiBaseUrl = 'http://localhost:8000'

function getApiUrl(endpoint, baseUrl = defaultApiBaseUrl) {
  return `${baseUrl.replace(/\/$/, '')}/${endpoint.replace(/^\//, '')}`
}

function getAuthHeaders() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function riskLabel(level) {
  const l = (level || '').toLowerCase()
  if (l === 'high') return 'High'
  if (l === 'low') return 'Low'
  return 'Medium'
}

export function mapAnalysisResponse(raw) {
  const compliance = raw.compliance_results || {}
  const risk = raw.risk_results || {}
  const violations = compliance.violations || []
  const riskItems = risk.risk_items || []
  const missing = compliance.missing_requirements || []

  // overall_risk_score is already normalized to 0–100 by risk_agent
  // (agents/risk_agent.py:_overall_score). Use it directly — do NOT re-normalize.
  const overallRisk = Math.round(
    Math.min(100, Math.max(0, risk.overall_risk_score || 0)),
  )

  const highRisk =
    violations.filter((v) => v.severity === 'high').length +
    riskItems.filter((r) => r.likelihood === 'high' && r.impact === 'high').length

  const findings = [
    ...violations.map((v) => ({
      clause: v.regulation || v.clause_id || 'Compliance',
      risk: riskLabel(v.severity),
      summary: v.description,
    })),
    ...riskItems.map((r) => ({
      clause: (r.risk_type || 'risk').replace(/_/g, ' '),
      risk: riskLabel(r.impact),
      summary: r.description,
    })),
  ]

  return {
    overallRisk,
    highRisk,
    gaps: missing.length,
    findings,
    raw, 
  }
}

export async function startAnalysis(file, baseUrl = defaultApiBaseUrl) {
  if (!file) throw new Error('No contract file provided.')
  
  const url = getApiUrl('/analyze', baseUrl)
  const formData = new FormData()
  formData.append('file', file) 

  const response = await fetch(url, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => response.statusText)
    throw new Error(`Backend error ${response.status}: ${errorText}`)
  }
  return await response.json()
}

export async function checkAnalysisStatus(contractId, baseUrl = defaultApiBaseUrl) {
  const url = getApiUrl(`/analyze/${contractId}/status`, baseUrl)
  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
  })
  if (!response.ok) {
    throw new Error('Failed to fetch status')
  }
  return await response.json()
}

export async function fetchReports(baseUrl = defaultApiBaseUrl) {
  const url = getApiUrl('/reports', baseUrl)
  const response = await fetch(url, { 
    method: 'GET',
    headers: getAuthHeaders()
  })
  if (!response.ok) throw new Error('Failed to fetch reports')
  return await response.json()
}

export async function fetchHistory(baseUrl = defaultApiBaseUrl) {
  const url = getApiUrl('/history', baseUrl)
  const response = await fetch(url, { 
    method: 'GET',
    headers: getAuthHeaders()
  })
  if (!response.ok) throw new Error('Failed to fetch history')
  return await response.json()
}

export function generateReportBlob(results, meta = {}) {
  const reportContent = [
    'Contract Review Report',
    '=====================',
    '',
    `Candidate: ${meta.candidate || 'N/A'}`,
    `File: ${meta.fileName || 'N/A'}`,
    '',
    `Overall risk: ${results.overallRisk ?? 'N/A'}%`,
    `High-risk clauses: ${results.highRisk ?? 'N/A'}`,
    `Compliance gaps: ${results.gaps ?? 'N/A'}`,
    '',
    'Findings:',
    ...(results.findings || []).map(
      (finding) => `- ${finding.clause} (${finding.risk}): ${finding.summary}`,
    ),
    '',
    'Raw results:',
    JSON.stringify(results, null, 2),
  ].join('\n')

  return new Blob([reportContent], { type: 'text/plain' })
}