export default function Modal({ open, onClose, title, children }) {
  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-6"
    >
      <div className="w-full max-w-2xl rounded-2xl bg-slate-950 p-6 shadow-xl">
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-2 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-slate-100"
          >
            Close
          </button>
        </div>
        <div className="mt-4 text-sm text-slate-300">{children}</div>
      </div>
    </div>
  )
}
