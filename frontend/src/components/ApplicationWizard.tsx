import { ArrowLeft, ArrowRight, Check, ChevronRight, DatabaseZap, Landmark, LoaderCircle, ShieldCheck, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from '../api'
import { errorText, money, payment, pct } from '../lib'
import type { Application, Company, Financials, Product, ProductType, Recommendation } from '../types'

export function ApplicationWizard({ company, products, onCreated, onCancel }: { company: Company; products: Product[]; onCreated: (a: Application) => void; onCancel: () => void }) {
  const [step, setStep] = useState(0)
  const [purpose, setPurpose] = useState('Пополнение оборотных средств')
  const [amount, setAmount] = useState(1_000_000)
  const [term, setTerm] = useState(24)
  const [collateral, setCollateral] = useState(false)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [productType, setProductType] = useState<ProductType>('WORKING_CAPITAL')
  const [figures, setFigures] = useState<Financials>({ annual_revenue: company.annual_revenue, monthly_net_profit: company.monthly_net_profit, current_debt_load: company.current_debt_load })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [filled, setFilled] = useState(false)
  const [consent, setConsent] = useState(false)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const product = products.find(p => p.product_type === productType)
  // The current scoring stub uses 19.5% for all products. Final offer always comes from API.
  const preliminaryPayment = payment(amount, term, 19.5)
  const dti = figures.monthly_net_profit > 0 ? (figures.current_debt_load + preliminaryPayment) / figures.monthly_net_profit : null
  async function next(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true)
    try {
      const result = await api.recommend({ purpose, amount, term_months: term, has_collateral: collateral })
      if (!alive.current) return
      setRecommendations(result)
      if (!result.length) { setError('Для этих параметров нет подходящих продуктов. Измените сумму, срок или готовность предоставить залог.'); return }
      setProductType(result[0].product.product_type); setStep(1)
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  async function prefill() {
    setBusy(true); setError('')
    try {
      const mock = await api.mock(company.inn)
      if (alive.current) { setFigures({ annual_revenue: mock.annual_revenue, monthly_net_profit: mock.monthly_net_profit, current_debt_load: mock.current_debt_load }); setFilled(true) }
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  async function submit(draft = false) {
    if (!draft && !consent) { setError('Подтвердите согласие на проверку данных.'); return }
    setBusy(true); setError('')
    try {
      const a = await api.create({ inn: company.inn, purpose, product_type: productType, requested_amount: amount,
        requested_term_months: term, has_collateral: collateral, submit: !draft, financial_overrides: figures })
      if (alive.current) onCreated(a)
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  return <div className="page-enter"><button className="back-link" onClick={onCancel}><ArrowLeft size={16} /> В кабинет</button><div className="page-title"><div className="eyebrow">ФИНАНСИРОВАНИЕ ПОД ВАШИ ЗАДАЧИ</div><h1>Большие планы начинаются здесь</h1><p>Расскажите о бизнесе. Мы подберём подходящие условия.</p></div><div className="wizard-progress">{['Ваши планы', 'Подходящий продукт', 'Данные и заявка'].map((label, i) => <div className={step >= i ? 'active' : ''} key={label}><span>{step > i ? <Check size={15} /> : `0${i + 1}`}</span>{label}{i < 2 && <ChevronRight size={16} />}</div>)}</div>
      <div className="wizard-layout"><section className="panel wizard-panel">
        {error && <div className="alert alert-red" role="alert">{error}</div>}
        {step === 0 && <form onSubmit={next}><div className="section-head"><div><h2>Что поможет вашему бизнесу?</h2><p>Начнём с цели, суммы и удобного срока.</p></div><Sparkles className="red" size={24} /></div><label className="field">Цель финансирования<select value={purpose} onChange={e => setPurpose(e.target.value)}><option>Пополнение оборотных средств</option><option>Закупка товаров и сырья</option><option>Покупка оборудования</option><option>Ремонт и расширение бизнеса</option><option>Кассовый разрыв и зарплата</option><option>Срочная небольшая покупка</option></select></label><div className="form-grid"><label className="field">Сумма, ₽<input type="number" min="50000" max="100000000" step="10000" required value={amount} onChange={e => setAmount(Number(e.target.value))} /></label><label className="field">Срок, месяцев<input type="number" min="1" max="120" required value={term} onChange={e => setTerm(Number(e.target.value))} /></label></div><label className="check-field"><input type="checkbox" checked={collateral} onChange={e => setCollateral(e.target.checked)} /><span>Готов предоставить залог<small>Может открыть доступ к инвестиционному кредиту</small></span></label><div className="form-actions"><button disabled={busy} className="btn btn-primary">{busy ? <LoaderCircle size={18} className="spin" /> : 'Найти подходящие продукты'}<ArrowRight size={17} /></button></div></form>}
        {step === 1 && <><div className="section-head"><div><h2>Решения для ваших планов</h2><p>Сравните условия и выберите продукт.</p></div></div><div className="product-options">{recommendations.map((r, i) => <button type="button" key={r.product.id} className={`product-option ${productType === r.product.product_type ? 'selected' : ''}`} onClick={() => setProductType(r.product.product_type)}><span className="product-option-head"><span className="product-symbol"><Landmark size={20} /></span><strong>{r.product.name}</strong>{i === 0 && <span className="badge badge-green">Рекомендуем</span>}<span className="radio-dot">{productType === r.product.product_type && <Check size={12} />}</span></span><p>{r.explanation}</p><span className="product-conditions"><span>Ставка по каталогу<strong>от {r.product.interest_rate}%</strong></span><span>Срок<strong>{r.product.min_term_months}–{r.product.max_term_months} мес.</strong></span><span>Сумма до<strong>{money(r.product.max_amount, true)}</strong></span></span></button>)}</div><div className="form-actions"><button className="btn btn-secondary" onClick={() => setStep(0)}><ArrowLeft size={16} /> Назад</button><button className="btn btn-primary" onClick={() => setStep(2)}>Продолжить <ArrowRight size={17} /></button></div></>}
        {step === 2 && <form onSubmit={e => { e.preventDefault(); void submit() }}><div className="section-head"><div><h2>Проверим данные компании</h2><p>{company.name} · ИНН {company.inn}</p></div></div><button type="button" className="autofill-btn" onClick={prefill} disabled={busy}><DatabaseZap size={20} /><span><strong>Предзаполнить данные из ФНС и БКИ</strong><small>{filled ? 'Данные получены. При необходимости отредактируйте показатели.' : 'Подтянем доступные сведения по ИНН автоматически'}</small></span>{busy ? <LoaderCircle size={18} className="spin" /> : <ArrowDownIcon />}</button><p className="form-note">Вы можете уточнить финансовые показатели перед отправкой. Внешние проверки сохранятся в досье отдельно.</p><div className="form-grid"><label className="field">Годовая выручка, ₽<input type="number" min="0" max="1000000000000000" required value={figures.annual_revenue} onChange={e => setFigures({ ...figures, annual_revenue: Number(e.target.value) })} /></label><label className="field">Чистая прибыль в месяц, ₽<input type="number" min="-1000000000000" max="1000000000000" required value={figures.monthly_net_profit} onChange={e => setFigures({ ...figures, monthly_net_profit: Number(e.target.value) })} /></label><label className="field">Текущие платежи по долгам, ₽/мес.<input type="number" min="0" max="1000000000000" required value={figures.current_debt_load} onChange={e => setFigures({ ...figures, current_debt_load: Number(e.target.value) })} /></label><label className="field">Запрашиваемая сумма, ₽<input type="number" min={product?.min_amount} max={product?.max_amount} required value={amount} onChange={e => setAmount(Number(e.target.value))} /></label><label className="field">Срок, месяцев<input type="number" min={product?.min_term_months} max={product?.max_term_months} required value={term} onChange={e => setTerm(Number(e.target.value))} /></label><label className="field">Цель финансирования<input minLength={2} maxLength={500} required value={purpose} onChange={e => setPurpose(e.target.value)} /></label></div><label className="check-field"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span>Согласен на обработку данных и демо-проверку в ФНС и БКИ<small>Используются синтетические данные хакатона</small></span></label><div className="form-actions"><button type="button" className="btn btn-secondary" onClick={() => setStep(1)} disabled={busy}>Назад</button><button className="btn btn-primary" disabled={busy}>{busy ? <LoaderCircle size={18} className="spin" /> : 'Отправить заявку'}<ArrowRight size={17} /></button></div><button type="button" className="text-btn save-draft" disabled={busy} onClick={() => { const form = document.querySelector<HTMLFormElement>('.wizard-panel form'); if (form?.reportValidity()) void submit(true) }}>Сохранить черновик</button></form>}
      </section><aside className="calculator"><div className="eyebrow">ВАШ ПЛАН ФИНАНСИРОВАНИЯ</div><h3>{money(amount)}</h3><p>Срок: {term || '—'} мес.</p><div className="calculator-rule" /><span className="muted">Предварительный платёж в месяц</span><strong className="payment-value">{money(preliminaryPayment)}</strong><div className="dti-heading"><span>Нагрузка на бизнес</span><strong>{dti === null ? 'Нет прибыли' : pct(dti)}</strong></div><div className="meter"><i style={{ width: `${Math.min((dti || 0) * 100, 100)}%`, background: dti === null || dti > .5 ? '#d49134' : '#087f5b' }} /></div><p className="calculator-advice">{dti === null ? 'Для обслуживания кредита необходим положительный денежный поток.' : dti > .5 ? 'Платежи займут больше половины прибыли. Банк может предложить меньшую сумму.' : 'Предварительная нагрузка оставляет вашему бизнесу запас на текущие расходы.'}</p><div className="calculator-foot"><ShieldCheck size={18} /><span>Предварительный расчет по ставке демо-скоринга 19,5%. Финальные условия — в решении банка.</span></div></aside></div>
    </div>
}
function ArrowDownIcon() { return <ArrowRight size={18} /> }
