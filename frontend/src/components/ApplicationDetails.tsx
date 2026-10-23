import { ArrowLeft, ArrowRight, Check, CheckCheck, CheckCircle2, ChevronDown, Download, FileCheck2, FileText, HandCoins, Info, LoaderCircle, ShieldCheck, Sparkles, Upload, XCircle } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from '../api'
import { date, docLabel, errorText, money, pct, statusLabel } from '../lib'
import type { Application } from '../types'
import { Confetti, Modal, StatusBadge } from './UI'

export function ApplicationDetails({ application: a, onBack, onChanged, bank = false }: { application: Application; onBack: () => void; onChanged: (a: Application) => void; bank?: boolean }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [code, setCode] = useState('')
  const [demoCode, setDemoCode] = useState('')
  const [consent, setConsent] = useState(false)
  const [signing, setSigning] = useState(false)
  const [celebrate, setCelebrate] = useState(false)
  const [uploadType, setUploadType] = useState(a.required_additional_docs[0] || '')
  const [file, setFile] = useState<File | null>(null)
  const [externalTab, setExternalTab] = useState<'egrul_egrip' | 'fns' | 'bki'>('egrul_egrip')
  const [showHistory, setShowHistory] = useState(bank)
  const [offeredIndex, setOfferedIndex] = useState(0)
  const [resendNote, setResendNote] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => { setUploadType(a.required_additional_docs[0] || '') }, [a.required_additional_docs.join('|')])
  const score = a.scoring_result
  const selectedOffer = a.offers[offeredIndex]
  async function act(fn: () => Promise<Application>) {
    setBusy(true); setError('')
    try { const updated = await fn(); if (alive.current) onChanged(updated) }
    catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  async function choose(index: number) {
    setBusy(true); setError(''); setOfferedIndex(index)
    try {
      const updated = await api.select(a.id, index)
      if (alive.current) onChanged(updated)
      const result = await api.code(a.id)
      if (alive.current) { setDemoCode(result.demo_code); setCode(''); setConsent(false); setSigning(true); setResendNote('') }
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  async function fund() {
    setBusy(true); setError('')
    try { const updated = await api.fund(a.id); if (alive.current) { onChanged(updated); setSigning(false); setCelebrate(true) } }
    catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  async function sign(e: FormEvent) {
    e.preventDefault(); if (!consent) return
    setBusy(true); setError('')
    try {
      const signed = await api.sign(a.id, code)
      if (alive.current) { onChanged(signed); setSigning(false) }
      const funded = await api.fund(a.id)
      if (alive.current) { onChanged(funded); setCelebrate(true) }
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  async function resend() {
    setBusy(true); setError('')
    try { const result = await api.code(a.id); if (alive.current) { setDemoCode(result.demo_code); setCode(''); setResendNote('Создан новый код. Предыдущий больше не действует.') } }
    catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  async function upload(e: FormEvent) {
    e.preventDefault(); if (!file) return
    if (file.size > 10 * 1024 * 1024 || !file.size) { setError('Выберите непустой файл размером до 10 МиБ.'); return }
    setBusy(true); setError('')
    try {
      await api.upload(a.id, uploadType, file)
      const updated = await api.application(a.id, bank)
      if (alive.current) { onChanged(updated); setFile(null); if (fileInput.current) fileInput.current.value = '' }
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  const stageStatuses = [['DRAFT'], ['SUBMITTED', 'EXTERNAL_CHECKS'], ['SCORING'], ['MANUAL_UNDERWRITING', 'NEED_MORE_INFO', 'OFFER_GENERATED', 'REJECTED'], ['ACCEPTED_BY_CLIENT', 'FUNDED']]
  const currentStage = stageStatuses.findIndex(group => group.includes(a.status))
  return <div className="page-enter detail-page">{celebrate && <Confetti />}<button className="back-link" onClick={onBack}><ArrowLeft size={16} />{bank ? 'К очереди заявок' : 'Мои заявки'}</button><div className="page-title detail-title"><div><div className="eyebrow">{bank ? 'ДОСЬЕ КЛИЕНТА' : 'ВАШ ПУТЬ К ФИНАНСИРОВАНИЮ'}</div><h1>Заявка №{a.id}</h1><p>{a.company.name} · {a.product.name}</p></div><StatusBadge status={a.status} /></div>
    <section className="panel tracker"><div className="tracker-top"><h2>Всё под контролем</h2><span className="muted text-xs">Обновлено {date(a.updated_at)} МСК</span></div><div className="tracker-steps">{['Заявка', 'Проверка ФНС / БКИ', 'Скоринг', 'Решение', 'Выдача средств'].map((label, i) => <div key={label} className={`tracker-step ${currentStage >= i ? 'passed' : ''} ${currentStage === i ? 'current' : ''} ${a.status === 'REJECTED' && i === 3 ? 'rejected-step' : ''}`}><span>{currentStage > i || a.status === 'FUNDED' ? <Check size={16} /> : a.status === 'REJECTED' && i === 3 ? <XCircle size={16} /> : i + 1}</span><strong>{label}</strong></div>)}</div></section>
    {error && <div className="alert alert-red" role="alert">{error}</div>}
    {a.status === 'DRAFT' && !bank && <section className="panel action-banner"><FileText size={27} /><div><h2>Черновик сохранён</h2><p>Проверьте параметры и отправьте заявку на рассмотрение.</p></div><button className="btn btn-primary" disabled={busy} onClick={() => void act(() => api.submit(a.id))}>Отправить заявку <ArrowRight size={16} /></button></section>}
    {a.status === 'OFFER_GENERATED' && <section className="decision-section"><div className="decision-heading"><span className="result-icon green"><CheckCheck size={24} /></span><div><h2>{score?.decision === 'ALTERNATIVE_OFFER' ? 'Финансирование на адаптированных условиях' : 'Хорошие новости — предложение готово'}</h2><p>{score?.decision === 'ALTERNATIVE_OFFER' ? 'Предлагаем меньшую сумму, чтобы платежи оставались комфортными для бизнеса.' : 'Выберите подходящие условия. Подписание займёт всего несколько шагов.'}</p></div></div><div className="requested-strip"><span>Вы запрашивали</span><strong>{money(a.requested_amount)}</strong><span>на {a.requested_term_months} мес.</span></div><div className="offers-grid">{a.offers.map((offer, index) => <article className={`offer-card ${index === 0 ? 'recommended' : ''}`} key={index}><div className="offer-card-top"><span className={`badge ${index === 0 ? 'badge-green' : 'badge-gray'}`}>{index === 0 ? 'Основное предложение' : 'Альтернативный вариант'}</span><LandmarkIcon /></div><h3>{money(offer.amount)}</h3><p>{offer.reason || (offer.amount < a.requested_amount ? 'Меньшая сумма — больше свободных средств на развитие' : 'Для ваших текущих задач и новых возможностей')}</p><dl className="detail-list"><div><dt>Ставка</dt><dd>{offer.interest_rate}% годовых</dd></div><div><dt>Срок</dt><dd>{offer.term_months} мес.</dd></div><div><dt>Ежемесячный платёж</dt><dd>{money(offer.monthly_payment)}</dd></div></dl>{!bank && <button className={`btn ${index === 0 ? 'btn-primary' : 'btn-secondary'}`} disabled={busy} onClick={() => void choose(index)}>{busy ? <LoaderCircle className="spin" size={17} /> : index === 0 ? 'Подписать договор ПЭП и зачислить' : 'Принять это предложение'}<ArrowRight size={17} /></button>}</article>)}</div></section>}
    {a.status === 'ACCEPTED_BY_CLIENT' && <section className="panel action-banner"><FileCheck2 size={30} className="green" /><div><h2>Договор подписан — осталось зачисление</h2><p>Условия зафиксированы. Подтвердите демо-зачисление средств на расчетный счёт.</p></div><button className="btn btn-primary" onClick={() => void fund()} disabled={busy}>Зачислить средства <HandCoins size={18} /></button></section>}
    {a.status === 'FUNDED' && <section className="funded-banner"><span className="funded-check"><Check size={30} /></span><div><span className="eyebrow">НОВЫЙ ШАГ ДЛЯ ВАШЕГО БИЗНЕСА</span><h2>{money(a.selected_offer?.amount || 0)} уже на вашем счёте</h2><p>Всё готово. Пусть ваши планы станут больше!</p><small>Демо-операция: {a.funding_reference}</small></div><Sparkles size={48} className="funded-spark" /></section>}
    {a.status === 'NEED_MORE_INFO' && <section className="panel documents-request"><div className="decision-heading"><span className="result-icon amber"><FileText size={24} /></span><div><h2>Нужно немного больше информации</h2><p>Загрузите документы ниже. Когда всё будет готово, заявка автоматически вернётся специалисту банка.</p></div></div><div className="bank-comment"><Info size={17} /><span>{[...a.history].reverse().find(h => h.status === 'NEED_MORE_INFO')?.comment}</span></div><div className="document-checklist">{a.required_additional_docs.map(doc => <div key={doc}><FileText size={18} /><span>{docLabel(doc)}</span><span className="badge badge-amber">Ожидаем</span></div>)}</div>{!bank && <form onSubmit={upload} className="upload-form"><label className="field">Тип документа<select value={uploadType} onChange={e => setUploadType(e.target.value)}>{a.required_additional_docs.map(doc => <option key={doc} value={doc}>{docLabel(doc)}</option>)}</select></label><label className="upload-zone"><Upload size={23} /><strong>{file?.name || 'Выберите файл для загрузки'}</strong><span>Непустой файл до 10 МиБ</span><input ref={fileInput} type="file" aria-label="Файл запрошенного документа" onChange={e => setFile(e.target.files?.[0] || null)} required /></label><button className="btn btn-primary" disabled={busy || !file}>{busy ? <LoaderCircle size={18} className="spin" /> : <Upload size={18} />} Отправить документ</button></form>}</section>}
    {a.status === 'MANUAL_UNDERWRITING' && <div className="alert alert-amber"><ShieldCheck size={23} /><div><strong>Ваша заявка у специалиста банка</strong><p>Мы изучаем документы и денежный поток. Решение появится здесь автоматически.</p></div></div>}
    {a.status === 'REJECTED' && <section className="panel rejection-panel"><div className="decision-heading"><span className="result-icon red"><XCircle size={24} /></span><div><h2>Сейчас мы не готовы предложить кредит</h2><p>Это решение по текущей заявке. Вот что можно улучшить перед новым обращением.</p></div></div><div className="alert alert-red">{a.rejection_reason}</div><ul className="advice-list"><li>Проверьте и погасите просроченную задолженность.</li><li>Уточните ограничения ФНС и урегулируйте налоговые долги.</li><li>Сократите действующие платежи или рассмотрите меньшую сумму.</li></ul></section>}
    <div className="detail-columns"><section className="panel"><div className="section-head"><h2>Параметры заявки</h2><FileText size={19} className="muted" /></div><dl className="detail-list"><div><dt>Сумма</dt><dd>{money(a.requested_amount)}</dd></div><div><dt>Срок</dt><dd>{a.requested_term_months} мес.</dd></div><div><dt>Продукт</dt><dd>{a.product.name}</dd></div><div><dt>Залог</dt><dd>{a.has_collateral ? 'Предусмотрен' : 'Без залога'}</dd></div><div><dt>ИНН</dt><dd>{a.company.inn}</dd></div></dl><div className="purpose-box"><small>Цель финансирования</small><p>{a.purpose}</p></div></section>
      {score && <section className="panel score-panel"><div className="section-head"><h2>{bank ? 'Скоринговая оценка' : 'Оценка финансового профиля'}</h2><span className={`grade grade-${score.risk_grade}`}>Grade {score.risk_grade}</span></div><div className="score-overview"><div className="score-ring" style={{ background: `conic-gradient(${score.risk_grade === 'D' ? '#EF3124' : '#087f5b'} ${score.score / 10}%, #edf0ef 0)` }}><div><strong>{score.score}</strong><small>из 1000 баллов</small></div></div><div className="score-numbers"><span>Долговая нагрузка<strong className={score.dti_ratio > .5 ? 'amber' : 'green'}>{pct(score.dti_ratio)}</strong></span><span>Вероятность дефолта<strong>{pct(score.probability_of_default)}</strong></span></div></div><p className="form-note">Оценка при подаче заявки, до ручного решения банка. DTI учитывает запрошенный кредит.</p></section>}
    </div>
    {score && <section className="panel"><div className="section-head"><h2>{a.status === 'REJECTED' ? 'Факторы решения' : 'Что повлияло на оценку'}</h2><span className="badge badge-gray">Демо-скоринг</span></div><div className="factor-list">{score.factors_explanation.map(factor => <div className="factor" key={factor.factor}><span className={`factor-icon ${factor.impact < 0 ? 'negative' : 'positive'}`}>{factor.impact < 0 ? <Info size={17} /> : <Check size={17} />}</span><p>{factor.description}</p><strong className={factor.impact < 0 ? 'red' : 'green'}>{factor.impact > 0 ? '+' : ''}{factor.impact}</strong></div>)}</div></section>}
    {bank && a.external_checks && <section className="panel"><div className="section-head"><h2>Внешние проверки</h2><span className="badge badge-gray">Снимок на момент подачи</span></div><div className="tabs" role="tablist" aria-label="Источники проверки">{([['egrul_egrip', 'ЕГРЮЛ / ЕГРИП'], ['fns', 'ФНС «Прозрачный бизнес»'], ['bki', 'БКИ']] as const).map(([key, label]) => <button key={key} role="tab" aria-selected={externalTab === key} onClick={() => setExternalTab(key)} className={externalTab === key ? 'active' : ''}>{label}</button>)}</div><dl className="detail-list external-data">{Object.entries(a.external_checks.external_data[externalTab]).map(([key, value]) => <div key={key}><dt>{externalLabel(key)}</dt><dd>{typeof value === 'boolean' ? value ? 'Да' : 'Нет' : String(value)}</dd></div>)}</dl>{a.external_checks.client_declared_financials && <div className="bank-comment"><Info size={18} /><span>В скоринге использованы уточненные клиентом показатели: выручка {money(a.external_checks.client_declared_financials.annual_revenue)}, прибыль {money(a.external_checks.client_declared_financials.monthly_net_profit)}/мес., платежи {money(a.external_checks.client_declared_financials.current_debt_load)}/мес. Исходный снимок моков сохранён.</span></div>}</section>}
    {a.documents.length > 0 && <section className="panel"><div className="section-head"><h2>Документы в заявке</h2><span className="badge badge-gray">{a.documents.length}</span></div><div className="document-checklist">{a.documents.map(doc => <div key={doc.id}><FileCheck2 size={20} className="green" /><span><strong>{docLabel(doc.document_type)}</strong><small>{doc.filename} · {Math.ceil(doc.size_bytes / 1024)} КБ · {date(doc.uploaded_at)}</small></span><a className="text-btn" href={api.documentUrl(a.id, doc.id)} download><Download size={16} /> Скачать</a></div>)}</div></section>}
    <section className="panel audit-panel"><button className="section-head audit-toggle" onClick={() => setShowHistory(!showHistory)} aria-expanded={showHistory}><h2>История движения заявки</h2><span>{a.history.length} событий <ChevronDown size={18} style={{ transform: showHistory ? 'rotate(180deg)' : undefined }} /></span></button>{showHistory && <ol className="audit-list">{[...a.history].reverse().map(entry => <li key={entry.id}><span className="audit-dot" /><div><div className="audit-entry-title"><strong>{statusLabel[entry.status]}</strong><span>{roleLabel(entry.role)}</span><time>{date(entry.timestamp)} МСК</time></div><p>{entry.comment}</p></div></li>)}</ol>}</section>
    {signing && <Modal title="Подпишите договор демо-ПЭП" onClose={() => { if (!busy) setSigning(false) }}><form onSubmit={sign}><div className="sign-summary"><ShieldCheck size={28} /><div><strong>{money(selectedOffer?.amount || 0)}</strong><p>{selectedOffer?.term_months} мес. · {selectedOffer?.interest_rate}% · {money(selectedOffer?.monthly_payment || 0)}/мес.</p></div></div><div className="alert alert-neutral">SMS симулируется. Ваш демо-код: <strong className="demo-code">{demoCode}</strong><span>Код действует 5 минут.</span></div>{resendNote && <p className="form-note" role="status">{resendNote}</p>}{error && <div className="alert alert-red" role="alert">{error}</div>}<label className="field">Код из SMS<input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ''))} placeholder="000000" className="otp-input" /></label><label className="check-field"><input type="checkbox" checked={consent} required onChange={e => setConsent(e.target.checked)} /><span>Принимаю выбранные условия и подтверждаю подписание договора демо-ПЭП</span></label><button className="btn btn-primary w-full" disabled={busy}>{busy ? <LoaderCircle size={18} className="spin" /> : <CheckCircle2 size={18} />} Подписать и зачислить средства</button><button type="button" className="text-btn resend-code" disabled={busy} onClick={() => void resend()}>Получить новый код</button></form></Modal>}
  </div>
}
function LandmarkIcon() { return <HandCoins size={21} className="muted" /> }
function externalLabel(key: string) { return ({ source: 'Источник', status: 'Статус регистрации', name: 'Наименование', okved: 'ОКВЭД', has_tax_debts: 'Налоговая задолженность', account_blocked: 'Блокировка счёта', score: 'Баллы БКИ', has_overdue_90_days: 'Просрочки 90+ дней', monthly_debt_payments: 'Текущие платежи, ₽/мес.' }[key] || key) }
function roleLabel(role: string) { return ({ SYSTEM: 'Система', CLIENT: 'Клиент', UNDERWRITER: 'Андеррайтер', BANK: 'Банк' }[role] || role) }
