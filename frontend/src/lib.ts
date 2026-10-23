import type { Status } from './types'
export const money = (n: number, compact = false) => new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0, ...(compact ? { notation: 'compact' as const } : {}) }).format(n)
export const number = (n: number) => new Intl.NumberFormat('ru-RU').format(n)
export const plural = (n: number, forms: [string, string, string]) => {
  const category = new Intl.PluralRules('ru-RU').select(n)
  return forms[category === 'one' ? 0 : category === 'few' ? 1 : 2]
}
export const pct = (ratio: number) => `${(ratio * 100).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}%`
export const date = (value: string) => new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' }).format(new Date(/[Zz]$|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`))
export const statusLabel: Record<Status, string> = {
  DRAFT: 'Черновик', SUBMITTED: 'Отправлена', EXTERNAL_CHECKS: 'Проверка данных', SCORING: 'Скоринг',
  NEED_MORE_INFO: 'Нужны документы', MANUAL_UNDERWRITING: 'На рассмотрении', OFFER_GENERATED: 'Предложение готово',
  ACCEPTED_BY_CLIENT: 'Договор подписан', FUNDED: 'Средства зачислены', REJECTED: 'Отказ',
}
export const docLabel = (key: string) => ({ BANK_STATEMENT_6M: 'Выписка по счету за 6 месяцев', MANAGEMENT_REPORT: 'Управленческая отчетность', CONTRACT: 'Договор с контрагентом' }[key] || key)
export const sector = (okved: string) => ({ '62': 'Информационные технологии', '56': 'Ресторанный бизнес', '41': 'Строительство', '47': 'Розничная торговля' }[okved.slice(0, 2)] || 'Предпринимательство')
export const payment = (amount: number, term: number, rate: number) => {
  if (!(amount > 0) || !(term > 0)) return 0
  const r = rate / 1200
  return r ? amount * r / (1 - (1 + r) ** -term) : amount / term
}
export const errorText = (e: unknown) => e instanceof Error ? e.message : 'Не удалось выполнить операцию'
