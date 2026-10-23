import { ArrowRight, ArrowUpRight, Building2, ChevronDown, CircleHelp, CreditCard, FileText, LayoutDashboard, LayoutList, LoaderCircle, Plus, RefreshCw, ShieldCheck, Sparkles, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from './api'
import { date, errorText, money } from './lib'
import type { Application, Company, NewsItem, Product } from './types'
import { ApplicationDetails } from './components/ApplicationDetails'
import { ApplicationWizard } from './components/ApplicationWizard'
import { BankQueue, UnderwriterPanel } from './components/BankWorkspace'
import { Dashboard } from './components/Dashboard'
import { Empty, Modal, Spinner, StatusBadge } from './components/UI'

type View = 'dashboard' | 'applications' | 'new'
function stored(key: string, fallback: string) { try { return localStorage.getItem(key) || fallback } catch { return fallback } }
function persist(key: string, value: string) { try { localStorage.setItem(key, value) } catch { /* Private browser mode still works. */ } }

export default function App() {
  const [role, setRole] = useState<'client' | 'bank'>(() => stored('credit-role', 'client') === 'bank' ? 'bank' : 'client')
  const [inn, setInn] = useState(() => { const value = stored('credit-inn', '7701111111'); return /^(?:[0-9]{10}|[0-9]{12})$/.test(value) ? value : '7701111111' })
  const [companies, setCompanies] = useState<Company[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [company, setCompany] = useState<Company | null>(null)
  const [applications, setApplications] = useState<Application[]>([])
  const [news, setNews] = useState<NewsItem[]>([])
  const [view, setView] = useState<View>('dashboard')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [opening, setOpening] = useState(false)
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [customOpen, setCustomOpen] = useState(false)
  const [customInn, setCustomInn] = useState('')
  const [customError, setCustomError] = useState('')
  const [customBusy, setCustomBusy] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [mobileMenu, setMobileMenu] = useState(false)
  const scope = useRef('')
  const currentContext = useRef(''); currentContext.current = `${role}:${inn}`
  const selected = applications.find(a => a.id === selectedId)

  useEffect(() => { persist('credit-role', role); persist('credit-inn', inn) }, [role, inn])
  useEffect(() => {
    const controller = new AbortController()
    let running = false
    const context = `${role}:${inn}`
    if (scope.current !== context) { setLoading(true); setApplications([]); setCompany(null); setNews([]); scope.current = context }
    async function load() {
      if (running) return
      running = true
      try {
        const [c, apps, n, demos, catalog] = await Promise.all([
          api.company(inn, controller.signal), api.applications(role === 'bank', inn, controller.signal),
          api.news(inn, controller.signal), api.companies(), api.products(),
        ])
        if (controller.signal.aborted) return
        setCompany(c); setApplications(apps); setNews(n); setCompanies(demos); setProducts(catalog); setError('')
      } catch (e) { if (!controller.signal.aborted) setError(errorText(e)) }
      finally { if (!controller.signal.aborted) setLoading(false); running = false }
    }
    void load()
    const timer = window.setInterval(() => { if (!document.hidden) void load() }, 5000)
    const onFocus = () => { void load() }; window.addEventListener('focus', onFocus)
    return () => { controller.abort(); window.clearInterval(timer); window.removeEventListener('focus', onFocus) }
  }, [inn, role, revision])

  function navigate(next: View) { setSelectedId(null); setView(next); setMobileMenu(false) }
  function changeCompany(next: string) { setSelectedId(null); setView('dashboard'); setInn(next); setMobileMenu(false) }
  function changeRole(next: 'client' | 'bank') { setSelectedId(null); setRole(next); setView('dashboard'); setMobileMenu(false) }
  function changed(a: Application) {
    setApplications(prev => [a, ...prev.filter(item => item.id !== a.id)].sort((x, y) => y.id - x.id))
    setRevision(n => n + 1)
  }
  async function open(a: Application) {
    const context = currentContext.current
    setOpening(true); setError('')
    try { const full = await api.application(a.id, role === 'bank'); if (currentContext.current === context) { setApplications(prev => prev.map(item => item.id === full.id ? full : item)); setSelectedId(full.id); setView('applications'); window.scrollTo({ top: 0, behavior: 'smooth' }) } }
    catch (e) { if (currentContext.current === context) setError(errorText(e)) }
    finally { setOpening(false) }
  }
  async function custom(e: FormEvent) {
    e.preventDefault(); setCustomBusy(true); setCustomError('')
    try { const c = await api.company(customInn); setCompany(c); changeCompany(c.inn); setCustomOpen(false); setCustomInn('') }
    catch (e) { setCustomError(errorText(e)) }
    finally { setCustomBusy(false) }
  }
  const nav = role === 'bank' ? [{ key: 'dashboard' as const, label: 'Кредитный конвейер', icon: LayoutList }] : [
    { key: 'dashboard' as const, label: 'Обзор кабинета', icon: LayoutDashboard },
    { key: 'applications' as const, label: 'Мои заявки', icon: FileText },
    { key: 'new' as const, label: 'Подобрать кредит', icon: CreditCard },
  ]
  return <div className="app-shell"><a href="#main-content" className="skip-link">Перейти к содержимому</a>
    <aside className={`sidebar ${mobileMenu ? 'mobile-open' : ''}`}><div className="sidebar-brand"><span className="alfa-logo">А<i /></span><span>Альфа<span className="brand-business">Бизнес</span></span><button className="icon-btn mobile-close" aria-label="Закрыть меню" onClick={() => setMobileMenu(false)}><X size={19} /></button></div><div className="workspace-label">{role === 'bank' ? 'РАБОЧЕЕ ПРОСТРАНСТВО БАНКА' : 'УМНЫЙ КРЕДИТНЫЙ КАБИНЕТ'}</div><nav aria-label="Главная навигация">{nav.map(({ key, label, icon: Icon }) => <button key={key} className={`nav-item ${view === key && !selectedId ? 'active' : selectedId && key === (role === 'bank' ? 'dashboard' : 'applications') ? 'active' : ''}`} onClick={() => navigate(key)}><Icon size={19} /><span>{label}</span>{key === 'applications' && applications.length > 0 && <span className="nav-count">{applications.length}</span>}</button>)}</nav>
      <div className="sidebar-support"><span className="support-icon"><Sparkles size={22} /></span><h3>Больше, чем кредит</h3><p>Возможности для бизнеса, подобранные под ваши задачи.</p><button onClick={() => { if (role === 'bank') changeRole('client'); navigate('dashboard') }}>Открыть мой кабинет <ArrowUpRight size={16} /></button></div><div className="sidebar-bottom"><button className="nav-item" onClick={() => setHelpOpen(true)}><CircleHelp size={19} />Как устроен кабинет</button><div className="sidebar-profile"><span className="avatar">{role === 'bank' ? 'АК' : 'АБ'}</span><div><strong>{role === 'bank' ? 'Андеррайтер' : 'Предприниматель'}</strong><span>Демонстрационный доступ</span></div><ShieldCheck size={16} className="muted" /></div></div></aside>
    <div className="app-main"><header className="demo-header"><div className="demo-header-top"><button className="icon-btn mobile-toggle" onClick={() => setMobileMenu(true)} aria-label="Открыть меню"><LayoutList size={22} /></button><div className="demo-tag"><span />ДЕМО-КАБИНЕТ</div><div className="role-switch" role="group" aria-label="Роль пользователя"><button aria-pressed={role === 'client'} className={role === 'client' ? 'active' : ''} onClick={() => changeRole('client')}><Building2 size={15} />Предприниматель</button><button aria-pressed={role === 'bank'} className={role === 'bank' ? 'active' : ''} onClick={() => changeRole('bank')}><ShieldCheck size={15} />Андеррайтер</button></div><div className="demo-header-right"><span className="live-dot" /><span>Хакатон · Альфа-Банк</span><button className="icon-btn" aria-label="Обновить данные" onClick={() => setRevision(n => n + 1)}><RefreshCw size={16} /></button></div></div><div className="context-header"><div className="context-breadcrumb">Бизнес-кабинет <span>/</span> {role === 'bank' ? 'Кредитный конвейер' : selected ? `Заявка №${selected.id}` : view === 'new' ? 'Новое финансирование' : view === 'applications' ? 'Мои заявки' : 'Обзор'}</div><div className="company-selector"><span className="company-avatar"><Building2 size={18} /></span><label className="sr-only" htmlFor="company-selector">Активная компания</label><select id="company-selector" value={inn} onChange={e => { if (e.target.value === 'custom') { setCustomOpen(true); return }; changeCompany(e.target.value) }}>{companies.map(c => <option value={c.inn} key={c.inn}>{c.name} · {c.inn}</option>)}{!companies.some(c => c.inn === inn) && <option value={inn}>{company?.name || 'Компания'} · {inn}</option>}<option value="custom">＋ Ввести свой ИНН</option></select><ChevronDown size={15} className="selector-chevron" /></div></div></header>
      <main id="main-content" className="main-content">{error && <div className="connection-error" role="alert"><div><strong>Не удалось обновить данные</strong><p>{error}</p></div><button className="btn btn-secondary" onClick={() => setRevision(n => n + 1)}><RefreshCw size={15} />Повторить</button></div>}{opening && <div className="opening-indicator" role="status"><LoaderCircle size={17} className="spin" />Открываем досье…</div>}
        {loading ? <Spinner /> : company ? selected ? <><ApplicationDetails key={`${role}-${selected.id}`} application={selected} bank={role === 'bank'} onBack={() => { setSelectedId(null); setView(role === 'bank' ? 'dashboard' : 'applications') }} onChanged={changed} />{role === 'bank' && <UnderwriterPanel key={`underwriter-${selected.id}`} application={selected} onChanged={changed} />}</> : role === 'bank' ? <BankQueue applications={applications} onOpen={a => void open(a)} /> : view === 'new' ? <ApplicationWizard key={inn} company={company} products={products} onCancel={() => navigate('dashboard')} onCreated={a => { changed(a); setSelectedId(a.id); setView('applications'); window.scrollTo(0, 0) }} /> : view === 'applications' ? <div className="page-enter"><div className="page-title"><div><span className="eyebrow">ИСТОРИЯ И НОВЫЕ ВОЗМОЖНОСТИ</span><h1>Мои заявки</h1><p>Все решения банка и документы — в одном месте.</p></div><button className="btn btn-primary" onClick={() => navigate('new')}><Plus size={18} />Новая заявка</button></div><div className="applications-list">{applications.length ? applications.map(a => <button key={a.id} className="panel application-list-card" onClick={() => void open(a)}><span className="product-symbol"><FileText size={22} /></span><span><strong>{a.product.name}</strong><small>№{a.id} · {date(a.created_at)}</small></span><StatusBadge status={a.status} /><strong className="application-list-sum">{money(a.requested_amount)}</strong><ArrowUpRight size={20} /></button>) : <Empty title="Здесь будет история ваших планов" text="Создайте первую заявку — мы подберём решение для бизнеса." action={<button className="btn btn-primary" onClick={() => navigate('new')}>Подобрать кредит <ArrowRight size={17} /></button>} />}</div></div> : <Dashboard company={company} applications={applications} news={news} onNew={() => navigate('new')} onApplication={a => void open(a)} onAll={() => navigate('applications')} /> : !error && <Empty title="Данные пока недоступны" text="Обновите страницу или выберите другую компанию." />}
      </main><footer className="app-footer"><span>Альфа-Банк · Умный кредитный кабинет</span><span>Хакатон 2026 <span>·</span> Синтетические данные</span></footer></div>
    {customOpen && <Modal title="Открыть компанию по ИНН" onClose={() => { if (!customBusy) setCustomOpen(false) }}><form onSubmit={custom}><p className="muted">Введите ИНН из 10 или 12 цифр. Для новой компании мы создадим воспроизводимый демо-профиль.</p><label className="field">ИНН компании<input value={customInn} onChange={e => setCustomInn(e.target.value.replace(/\D/g, ''))} inputMode="numeric" pattern="(?:[0-9]{10}|[0-9]{12})" minLength={10} maxLength={12} placeholder="Например, 7812345678" required /></label>{customError && <div className="alert alert-red" role="alert">{customError}</div>}<button className="btn btn-primary w-full" disabled={customBusy}>{customBusy ? <LoaderCircle size={18} className="spin" /> : 'Открыть кабинет'}<ArrowRight size={17} /></button></form></Modal>}
    {helpOpen && <Modal title="Один кабинет — два взгляда" onClose={() => setHelpOpen(false)}><div className="help-content"><p>Переключайте роль в верхней панели: предприниматель подаёт заявку и подписывает договор, андеррайтер проверяет досье и принимает решение.</p><ol><li><strong>АльфаТех:</strong> готовое одобрение и демо-выдача.</li><li><strong>Сеть кофеен:</strong> адаптированные условия и выбор альтернативы.</li><li><strong>СтройМастер:</strong> документы, затем ручное решение.</li><li><strong>Вектор Торг:</strong> причины отказа и рекомендации.</li></ol><p>Лента рекомендаций обновляется при смене компании и статуса заявки. Данные синтетические; реальных переводов и запросов в государственные сервисы нет.</p><a className="text-btn" href="http://localhost:8000/docs" target="_blank" rel="noreferrer">Открыть Swagger API <ArrowUpRight size={16} /></a></div></Modal>}
  </div>
}
