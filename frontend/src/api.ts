import type { Application, ApplicationCreate, Company, Decision, NewsItem, Product, Recommendation } from './types'

// Same-origin /api uses Vite's local proxy and Nginx's Docker proxy.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
export class ApiError extends Error { constructor(public status: number, message: string) { super(message) } }

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try { response = await fetch(`${API_BASE}${path}`, options) }
  catch (e) {
    if (e instanceof Error && e.name === 'AbortError') throw e
    throw new Error('Нет соединения с сервером. Проверьте, что backend запущен, и повторите запрос.')
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((d: { loc?: string[]; msg?: string }) => `${d.loc?.slice(1).join('.') || 'Запрос'}: ${d.msg}`).join('; ')
      : `Сервер вернул ошибку ${response.status}. Повторите запрос.`
    throw new ApiError(response.status, message)
  }
  return response.json() as Promise<T>
}
const json = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const api = {
  companies: () => request<Company[]>('/companies/demo'),
  company: (inn: string, signal?: AbortSignal) => request<Company>(`/companies/${inn}`, { signal }),
  mock: (inn: string) => request<Company>(`/mocks/company-by-inn/${inn}`),
  products: () => request<Product[]>('/products'),
  news: (inn: string, signal?: AbortSignal) => request<NewsItem[]>(`/news/personalized/${inn}`, { signal }),
  recommend: (body: { purpose: string; amount: number; term_months: number; has_collateral: boolean }) => request<Recommendation[]>('/products/recommend', json(body)),
  async applications(bank: boolean, inn: string, signal?: AbortSignal) {
    const all: Application[] = []
    for (let offset = 0; ; offset += 100) {
      const page = await request<Application[]>(`${bank ? '/bank' : ''}/applications?limit=100&offset=${offset}${bank ? '' : `&inn=${inn}`}`, { signal })
      all.push(...page)
      if (page.length < 100) return all
    }
  },
  application: (id: number, bank = false) => request<Application>(`${bank ? '/bank' : ''}/applications/${id}`),
  create: (body: ApplicationCreate) => request<Application>('/applications', json(body)),
  submit: (id: number) => request<Application>(`/applications/${id}/submit`, { method: 'POST' }),
  select: (id: number, offer_index: number) => request<Application>(`/applications/${id}/select-offer`, json({ offer_index })),
  code: (id: number) => request<{ demo_code: string; expires_in_seconds: number }>(`/applications/${id}/sign/request-code`, { method: 'POST' }),
  sign: (id: number, code: string) => request<Application>(`/applications/${id}/sign`, json({ code, consent: true })),
  fund: (id: number) => request<Application>(`/bank/applications/${id}/fund`, { method: 'POST' }),
  decision: (id: number, body: Decision) => request<Application>(`/bank/applications/${id}/decision`, json(body)),
  upload: (id: number, document_type: string, file: File) => {
    const body = new FormData(); body.append('document_type', document_type); body.append('file', file)
    return request(`/applications/${id}/documents`, { method: 'POST', body })
  },
  documentUrl: (id: number, documentId: number) => `${API_BASE}/applications/${id}/documents/${documentId}/download`,
}
