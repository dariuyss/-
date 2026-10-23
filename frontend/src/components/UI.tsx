import { ArrowUpRight, Check, LoaderCircle, X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'
import { statusLabel } from '../lib'
import type { Status } from '../types'

export function StatusBadge({ status }: { status: Status }) {
  const tone = ['OFFER_GENERATED', 'FUNDED', 'ACCEPTED_BY_CLIENT'].includes(status) ? 'green' : status === 'REJECTED' ? 'red' : ['NEED_MORE_INFO', 'MANUAL_UNDERWRITING'].includes(status) ? 'amber' : 'gray'
  return <span className={`badge badge-${tone}`}><span className="badge-dot" />{statusLabel[status]}</span>
}
export function Spinner({ label = 'Загружаем данные…' }: { label?: string }) {
  return <div className="loading" role="status"><LoaderCircle size={22} className="spin" />{label}</div>
}
export function Empty({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return <div className="empty"><div className="empty-icon"><ArrowUpRight size={28} /></div><h3>{title}</h3><p>{text}</p>{action}</div>
}
export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  const close = useRef(onClose); close.current = onClose
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null
    const old = document.body.style.overflow; document.body.style.overflow = 'hidden'
    const nodes = () => Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]') || [])
    nodes()[0]?.focus()
    const keyboard = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close.current()
      if (e.key === 'Tab') {
        const items = nodes(), first = items[0], last = items.at(-1)
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
      }
    }
    document.addEventListener('keydown', keyboard)
    return () => { document.body.style.overflow = old; document.removeEventListener('keydown', keyboard); before?.focus() }
  }, [])
  return <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}><div ref={ref} className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div className="section-head"><h2 id="modal-title">{title}</h2><button className="icon-btn" aria-label="Закрыть" onClick={onClose}><X size={21} /></button></div>{children}</div></div>
}
export function Confetti() {
  return <div className="confetti" aria-hidden="true">{Array.from({ length: 32 }, (_, i) => <i key={i} style={{ left: `${(i * 37) % 100}%`, animationDelay: `${(i % 6) * .13}s`, background: ['#EF3124', '#ffbf69', '#087f5b', '#a8d5c1'][i % 4], transform: `rotate(${i * 28}deg)` }} />)}</div>
}
export function StepCheck({ complete }: { complete: boolean }) { return <span className={`step-circle ${complete ? 'complete' : ''}`}>{complete && <Check size={14} />}</span> }
