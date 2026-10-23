"""Deterministic DEMO stub. Replace evaluate_application with ML inference later.

current_debt_load is the sum of existing MONTHLY debt payments in RUB.
interest_rate is annual percent; PD is a synthetic demonstration value.
"""
from .schemas import ScoringInput, ScoringResult


def monthly_payment(amount: float, term: int, rate: float) -> float:
    r = rate / 1200
    return round(amount / term if r == 0 else amount * r / (1 - (1 + r) ** -term), 2)


def make_offer(amount: float, term: int, rate: float, product_type: str) -> dict:
    return {"amount": round(amount, 2), "term_months": term, "interest_rate": rate,
            "monthly_payment": monthly_payment(amount, term, rate), "product_type": product_type}


def evaluate_application(data: ScoringInput) -> ScoringResult:
    offer = make_offer(data.requested_amount, data.requested_term_months, 19.5, data.product_type)
    dti = (data.current_debt_load + offer["monthly_payment"]) / max(data.monthly_net_profit, 1.0)
    decision = "APPROVED"
    if data.has_overdue_90_days or data.has_tax_debts or data.monthly_net_profit <= 0:
        decision = "REJECTED"
    elif data.inn == "7703333333" or data.credit_history_score < 650 or data.business_age_months < 12:
        decision = "MANUAL_REVIEW"
    elif data.inn == "7702222222" or dti > 0.5:
        decision = "ALTERNATIVE_OFFER"
    scores = {"APPROVED": 920, "ALTERNATIVE_OFFER": 740, "MANUAL_REVIEW": 580, "REJECTED": 180}
    grades = {"APPROVED": "A", "ALTERNATIVE_OFFER": "B", "MANUAL_REVIEW": "C", "REJECTED": "D"}
    alternatives = []
    docs = []
    if decision == "ALTERNATIVE_OFFER":
        capacity = data.monthly_net_profit * 0.5 - data.current_debt_load
        if capacity <= 0:
            decision = "MANUAL_REVIEW"
        else:
            # Calculate per-unit payment without rounding to kopecks.
            r = 19.5 / 1200
            unit = r / (1 - (1 + r) ** -data.requested_term_months)
            amount = min(data.requested_amount * 0.6, capacity / unit)
            reduced = make_offer(max(1.0, amount), data.requested_term_months, 19.5, data.product_type)
            offer = reduced
            alternatives = [{**make_offer(max(1.0, amount * .8), data.requested_term_months, 19.5, data.product_type),
                             "reason": "Еще меньшая сумма снижает ежемесячный платеж и оставляет резерв ликвидности"}]
    if decision == "MANUAL_REVIEW":
        docs = ["BANK_STATEMENT_6M", "MANAGEMENT_REPORT"]
    factors = [
        {"factor": "credit_history", "impact": -400 if data.has_overdue_90_days else 100,
         "description": "Просрочки 90+ дней" if data.has_overdue_90_days else "Нет просрочек 90+ дней"},
        {"factor": "dti", "impact": -120 if dti > 0.5 else 80,
         "description": f"Платежи с учетом запрошенного кредита / месячная прибыль: {dti:.2f}"},
        {"factor": "tax_debts", "impact": -250 if data.has_tax_debts else 30,
         "description": "Есть налоговая задолженность" if data.has_tax_debts else "Нет налоговой задолженности"},
        {"factor": "demo_stub", "impact": 0, "description": "Демонстрационные правила; результат не является решением реального банка"},
    ]
    return ScoringResult(score=scores[decision], probability_of_default={"A": .01, "B": .06, "C": .18, "D": .7}[grades[decision]],
                         risk_grade=grades[decision], decision=decision, dti_ratio=round(dti, 4),
                         factors_explanation=factors, recommended_offer=offer if decision in {"APPROVED", "ALTERNATIVE_OFFER"} else None,
                         alternative_offers=alternatives, required_additional_docs=docs)
