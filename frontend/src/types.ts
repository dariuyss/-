export type ProductType = 'WORKING_CAPITAL' | 'INVESTMENT' | 'OVERDRAFT' | 'EXPRESS'
export type Status = 'DRAFT' | 'SUBMITTED' | 'EXTERNAL_CHECKS' | 'SCORING' | 'NEED_MORE_INFO' | 'MANUAL_UNDERWRITING' | 'OFFER_GENERATED' | 'ACCEPTED_BY_CLIENT' | 'FUNDED' | 'REJECTED'
export type Grade = 'A' | 'B' | 'C' | 'D'
export interface Financials { annual_revenue: number; monthly_net_profit: number; current_debt_load: number }
export interface Company extends Financials {
  id: number; inn: string; name: string; org_type: 'IP' | 'OOO'; okved: string; business_age_months: number
  credit_history_score: number; has_overdue_90_days: boolean; has_tax_debts: boolean; fns_blocked: boolean; is_demo: boolean
  external_data: { is_mock: boolean; egrul_egrip: Record<string, unknown>; fns: Record<string, unknown>; bki: Record<string, unknown> }
}
export interface Product {
  id: number; product_type: ProductType; name: string; description: string; min_amount: number; max_amount: number
  min_term_months: number; max_term_months: number; interest_rate: number; collateral_required: boolean
}
export interface Offer { amount: number; term_months: number; interest_rate: number; monthly_payment: number; product_type: ProductType; reason?: string }
export interface ScoringResult {
  model_name?: string; model_version?: string; policy_version?: string
  score: number; probability_of_default: number; risk_grade: Grade
  decision: 'APPROVED' | 'ALTERNATIVE_OFFER' | 'MANUAL_REVIEW' | 'REJECTED'; dti_ratio: number
  factors_explanation: { factor: string; impact: number; description: string }[]
  recommended_offer: Offer | null; alternative_offers: Offer[]; required_additional_docs: string[]
}
export interface HistoryEntry { id: number; status: Status; role: string; comment: string; timestamp: string }
export interface DocumentInfo { id: number; document_type: string; filename: string; content_type: string; size_bytes: number; sha256: string; uploaded_at: string }
export interface Application {
  id: number; company: Company; product: Product; purpose: string; requested_amount: number; requested_term_months: number
  has_collateral: boolean; status: Status; scoring_input: Record<string, unknown> | null; scoring_result: ScoringResult | null
  external_checks: (Company & { client_declared_financials?: Financials }) | null; offers: Offer[]; selected_offer: Offer | null
  required_additional_docs: string[]; rejection_reason: string | null; signed_at: string | null; funded_at: string | null
  funding_reference: string | null; created_at: string; updated_at: string; version: number
  history: HistoryEntry[]; documents: DocumentInfo[]
}
export interface NewsItem { id: number; title: string; content: string; category: string; published_at: string; personalization_reason: string; is_demo: boolean }
export interface Recommendation { product: Product; relevance_score: number; explanation: string }
export interface ApplicationCreate {
  inn: string; product_type: ProductType; purpose: string; requested_amount: number; requested_term_months: number
  has_collateral: boolean; submit: boolean; financial_overrides?: Financials
}
export interface Decision { decision: 'APPROVE' | 'CHANGE_TERMS' | 'REQUEST_DOCUMENTS' | 'REJECT'; comment: string; offer?: Offer; required_additional_docs?: string[] }
