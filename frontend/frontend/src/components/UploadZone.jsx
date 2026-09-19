import { useRef, useState } from 'react'
import { FileUp } from 'lucide-react'

// Must match the backend's SUPPORTED_EXTENSIONS (api/analyze.py).
const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.docm']
const ACCEPT_ATTR = ACCEPTED_EXTENSIONS.join(',')

function isSupported(file) {
  const name = (file?.name || '').toLowerCase()
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
}

export function UploadZone({ selectedFile, onFileSelect }) {
  const inputRef = useRef(null)
  const [dragActive, setDragActive] = useState(false)
  const [error, setError] = useState('')

  const handleButtonClick = () => {
    inputRef.current?.click()
  }

  const accept = (file) => {
    if (!file) return
    if (!isSupported(file)) {
      setError(`Unsupported file type. Please upload a ${ACCEPTED_EXTENSIONS.join(', ')} file.`)
      return
    }
    setError('')
    onFileSelect(file)
  }

  const handleFileChange = (event) => {
    accept(event.target.files?.[0])
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setDragActive(false)
    accept(event.dataTransfer.files?.[0])
  }

  const handleDragOver = (event) => {
    event.preventDefault()
    setDragActive(true)
  }

  const handleDragLeave = () => {
    setDragActive(false)
  }

  return (
    <div className="space-y-4">
      <div
        className={`rounded-2xl border-2 border-dashed p-6 text-slate-300 transition ${
          dragActive ? 'border-cyan-400/70 bg-slate-900/80' : 'border-slate-700 bg-slate-900/70'
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <div className="flex flex-col items-center justify-center gap-4 text-center">
          <FileUp className="h-10 w-10 text-cyan-300" />
          <div>
            <p className="font-medium text-slate-100">Drag and drop a contract file</p>
            <p className="mt-1 text-sm text-slate-400">Supported types: PDF, DOCX, DOCM.</p>
          </div>
          <button
            type="button"
            onClick={handleButtonClick}
            className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-4 py-2 text-sm font-medium text-cyan-300 transition hover:bg-cyan-500/15"
          >
            Choose a file
          </button>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_ATTR}
          className="sr-only"
          onChange={handleFileChange}
        />
      </div>

      {error && (
        <p className="rounded-2xl border border-rose-500/20 bg-rose-500/5 px-4 py-2 text-sm text-rose-200">
          {error}
        </p>
      )}

      <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-300">
        <p className="font-semibold text-slate-200">Selected contract</p>
        <p className="mt-2 text-slate-400">{selectedFile ? selectedFile.name : 'No file selected yet.'}</p>
        {selectedFile && (
          <p className="mt-1 text-xs text-slate-500">Size: {(selectedFile.size / 1024).toFixed(1)} KB</p>
        )}
      </div>
    </div>
  )
}
