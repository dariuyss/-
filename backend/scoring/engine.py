"""Synthetic ML PD plus separate, explicit demonstration credit policy.

PD uses current monthly debt payments. Offer affordability also includes the new
loan payment. Policy thresholds are demo choices, not validated bank policy.
"""
from functools import lru_cache
import hashlib
import logging
import math

from fastapi import HTTPException
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier

from .schemas import ScoringInput, ScoringResult
from .train_model import MODEL_PATH, _load_model, predict_pd_from_features

logger = logging.getLogger(__name__)
MODEL_NAME = "hist_gradient_boosting_sigmoid"
POLICY_VERSION = "demo-ml-v1"
# Model risk routes to a human, not automatic rejection based only on synthetic PD.
REVIEW_PD_THRESHOLD = .35


@lru_cache(maxsize=1)
def model_metadata() -> dict:
    model = _load_model()
    if not isinstance(model, CalibratedClassifierCV) or not isinstance(
        model.estimator.named_steps.get("classifier"), HistGradientBoostingClassifier
    ):
        raise RuntimeError("Expected the calibrated gradient boosting scoring model")
    return {"model_name": MODEL_NAME,
            "model_version": hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
            "policy_version": POLICY_VERSION}


def monthly_payment(amount: float, term: int, rate: float) -> float:
    r = rate / 1200
    return round(amount / term if r == 0 else amount * r / (1 - (1 + r) ** -term), 2)


def make_offer(amount: float, term: int, rate: float, product_type: str) -> dict:
    return {"amount": round(amount, 2), "term_months": term, "interest_rate": rate,
            "monthly_payment": monthly_payment(amount, term, rate), "product_type": product_type}


def outside_training_domain(data: ScoringInput) -> bool:
    margin = data.monthly_net_profit * 12 / max(data.annual_revenue, 1.)
    return not (3 <= data.business_age_months <= 180
        and 1_500_000 <= data.annual_revenue <= 200_000_000
        and 300_000 <= data.requested_amount <= 25_000_000
        and 300 <= data.credit_history_score <= 850
        and .05 <= margin <= .25)


def evaluate_application(data: ScoringInput) -> ScoringResult:
    try:
        pd_value = predict_pd_from_features(data.model_dump())
        if not math.isfinite(pd_value) or not 0 <= pd_value <= 1:
            raise ValueError("Model returned an invalid probability")
        metadata = model_metadata()
    except Exception as exc:
        logger.exception("ML scoring unavailable")
        raise HTTPException(503, "ML-скоринг временно недоступен. Заявка не отправлена; повторите позже.") from exc

    offer = make_offer(data.requested_amount, data.requested_term_months, 19.5, data.product_type)
    dti = (data.current_debt_load + offer["monthly_payment"]) / max(data.monthly_net_profit, 1.0)
    out_of_domain = outside_training_domain(data)
    decision = "APPROVED"
    if (data.has_overdue_90_days or data.has_tax_debts or data.has_fns_account_blockings
            or data.monthly_net_profit <= 0):
        decision = "REJECTED"
    elif (out_of_domain or pd_value >= REVIEW_PD_THRESHOLD
          or data.credit_history_score < 650 or data.business_age_months < 12):
        decision = "MANUAL_REVIEW"
    elif dti > .5:
        decision = "ALTERNATIVE_OFFER"

    alternatives, docs = [], []
    if decision == "ALTERNATIVE_OFFER":
        capacity = data.monthly_net_profit * .5 - data.current_debt_load
        if capacity <= 0:
            decision = "MANUAL_REVIEW"
        else:
            r = 19.5 / 1200
            unit = r / (1 - (1 + r) ** -data.requested_term_months)
            amount = min(data.requested_amount * .6, capacity / unit)
            offer = make_offer(max(1., amount), data.requested_term_months, 19.5, data.product_type)
            alternatives = [{**make_offer(max(1., amount * .8), data.requested_term_months, 19.5, data.product_type),
                "reason": "Меньшая сумма снижает ежемесячный платеж и оставляет резерв ликвидности"}]
    if decision == "MANUAL_REVIEW":
        docs = ["BANK_STATEMENT_6M", "MANAGEMENT_REPORT"]

    # Score/grade are display mappings of PD, not separate fitted models.
    grade = "A" if pd_value < .10 else "B" if pd_value < .20 else "C" if pd_value < .35 else "D"
    # Observations and policy reasons, NOT fabricated SHAP contributions.
    factors = [
        {"factor": "ml_pd", "impact": 0,
         "description": f"Градиентный бустинг: PD {pd_value:.2%}. Модель обучена на синтетических данных."},
        {"factor": "dti", "impact": 0,
         "description": f"Правило платежеспособности: платежи с новым кредитом / месячная прибыль = {dti:.2f}; ориентир 0.50."},
        {"factor": "credit_history", "impact": 0,
         "description": f"БКИ {data.credit_history_score}; просрочка 30+: {data.has_overdue_30_days}; 90+: {data.has_overdue_90_days}."},
        {"factor": "tax_status", "impact": 0,
         "description": f"Налоговый долг: {data.has_tax_debts}; блокировка ФНС: {data.has_fns_account_blockings}."},
        {"factor": "policy", "impact": 0,
         "description": "Решение учитывает PD и демонстрационные правила банка. Перечислены факты и правила, не вклады признаков ML."},
    ]
    if out_of_domain:
        factors.append({"factor": "outside_training_domain", "impact": 0,
            "description": "Параметры вне диапазона обучения: PD ориентировочная; автоматическое одобрение недоступно."})
    return ScoringResult(**metadata, score=round(1000 * (1 - pd_value)),
        probability_of_default=pd_value, risk_grade=grade, decision=decision,
        dti_ratio=round(dti, 4), factors_explanation=factors,
        recommended_offer=offer if decision in {"APPROVED", "ALTERNATIVE_OFFER"} else None,
        alternative_offers=alternatives, required_additional_docs=docs)
