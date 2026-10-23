"""State transitions and business operations. Caller owns the transaction."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import ApplicationHistory, LoanApplication, utcnow
from ..schemas import DecisionRequest
from ..scoring.engine import evaluate_application, make_offer
from ..scoring.schemas import ScoringInput
from .external_mocks import company_by_inn

TRANSITIONS = {
    "DRAFT": {"SUBMITTED"},
    "SUBMITTED": {"EXTERNAL_CHECKS"},
    "EXTERNAL_CHECKS": {"SCORING", "REJECTED"},
    "SCORING": {"MANUAL_UNDERWRITING", "OFFER_GENERATED", "REJECTED"},
    "MANUAL_UNDERWRITING": {"NEED_MORE_INFO", "OFFER_GENERATED", "REJECTED"},
    "NEED_MORE_INFO": {"MANUAL_UNDERWRITING", "REJECTED"},
    "OFFER_GENERATED": {"ACCEPTED_BY_CLIENT"},
    "ACCEPTED_BY_CLIENT": {"FUNDED"},
    "FUNDED": set(), "REJECTED": set(),
}


def require_status(application: LoanApplication, *statuses: str):
    if application.status not in statuses:
        raise HTTPException(409, f"Операция недоступна в статусе {application.status}; ожидается {', '.join(statuses)}")


def record(db: Session, application: LoanApplication, role: str, comment: str):
    application.updated_at = utcnow()
    application.history.append(ApplicationHistory(status=application.status, role=role, comment=comment))
    db.flush()


def transition(db: Session, application: LoanApplication, target: str, role: str, comment: str):
    if target not in TRANSITIONS.get(application.status, set()):
        raise HTTPException(409, f"Недопустимый переход {application.status} → {target}")
    application.status = target
    record(db, application, role, comment)


def validate_product(application: LoanApplication):
    p = application.product
    if not p.min_amount <= application.requested_amount <= p.max_amount:
        raise HTTPException(422, f"Сумма для продукта: {p.min_amount}–{p.max_amount} руб.")
    if not p.min_term_months <= application.requested_term_months <= p.max_term_months:
        raise HTTPException(422, f"Срок для продукта: {p.min_term_months}–{p.max_term_months} месяцев")
    if p.collateral_required and not application.has_collateral:
        raise HTTPException(422, "Для выбранного продукта требуется залог")


def submit_application(db: Session, application: LoanApplication):
    require_status(application, "DRAFT")
    validate_product(application)
    transition(db, application, "SUBMITTED", "CLIENT", "Заявка отправлена предпринимателем")
    transition(db, application, "EXTERNAL_CHECKS", "SYSTEM", "Запущены проверки ЕГРЮЛ/ЕГРИП, ФНС и БКИ")
    snapshot = company_by_inn(application.company.inn)
    application.external_checks = snapshot
    fields = ScoringInput.model_fields
    values = {k: v for k, v in snapshot.items() if k in fields}
    # Required source fields: missing external information is never treated as False/0.
    try:
        values.update(
            has_overdue_30_days=snapshot["external_data"]["bki"]["has_overdue_30_days"],
            has_fns_account_blockings=snapshot["external_data"]["fns"]["account_blocked"],
            tax_payments_to_revenue_ratio=snapshot["external_data"]["fns"]["tax_payments_to_revenue_ratio"],
        )
    except KeyError as exc:
        raise HTTPException(503, "Не получены обязательные данные для ML-скоринга") from exc
    overrides = (application.scoring_input or {}).get("financial_overrides")
    if overrides:
        values.update(overrides)
        application.external_checks = {**snapshot, "client_declared_financials": overrides}
    values.update(requested_amount=application.requested_amount, requested_term_months=application.requested_term_months,
                  product_type=application.product.product_type)
    from pydantic import ValidationError
    try:
        data = ScoringInput.model_validate(values)
    except ValidationError as exc:
        raise HTTPException(503, "Некорректные данные источника скоринга") from exc
    application.scoring_input = data.model_dump()
    if overrides:
        record(db, application, "CLIENT", "Для скоринга использованы заявленные клиентом выручка, прибыль и ежемесячные платежи; внешние проверки сохранены отдельно")
    transition(db, application, "SCORING", "SYSTEM", "Данные обогащены; вызван ML-скоринг (градиентный бустинг, синтетическая модель)")
    result = evaluate_application(data)
    application.scoring_result = result.model_dump()
    if snapshot["fns_blocked"] or result.decision == "REJECTED":
        reasons = []
        if snapshot["fns_blocked"]:
            reasons.append("Блокировка счета ФНС")
        if data.has_overdue_90_days:
            reasons.append("Просрочки по кредитам 90+ дней")
        if data.has_tax_debts:
            reasons.append("Налоговая задолженность")
        application.rejection_reason = "; ".join(reasons) or "Недостаточный денежный поток для обслуживания кредита"
        transition(db, application, "REJECTED", "SYSTEM", application.rejection_reason)
    elif result.decision == "MANUAL_REVIEW":
        transition(db, application, "MANUAL_UNDERWRITING", "SYSTEM", "Пограничные показатели: требуется проверка андеррайтера")
        if result.required_additional_docs:
            application.required_additional_docs = result.required_additional_docs
            transition(db, application, "NEED_MORE_INFO", "SYSTEM", "Для ручного рассмотрения нужны: " + ", ".join(result.required_additional_docs))
    else:
        offers = ([result.recommended_offer] if result.recommended_offer else []) + result.alternative_offers
        # Never show offers outside the selected product's limits.
        application.offers = [o for o in offers if application.product.min_amount <= o["amount"] <= application.product.max_amount]
        if not application.offers:
            transition(db, application, "MANUAL_UNDERWRITING", "SYSTEM", "Автоматический оффер ниже лимита продукта; нужна ручная проверка")
        else:
            transition(db, application, "OFFER_GENERATED", "SYSTEM", "Сформировано одобрение" if result.decision == "APPROVED" else "Предложена меньшая сумма с учетом долговой нагрузки")
    db.flush()


def bank_decision(db: Session, application: LoanApplication, data: DecisionRequest):
    require_status(application, "MANUAL_UNDERWRITING", "NEED_MORE_INFO")
    if data.decision == "REJECT":
        application.rejection_reason = data.comment
        transition(db, application, "REJECTED", "UNDERWRITER", data.comment)
    elif data.decision == "REQUEST_DOCUMENTS":
        application.required_additional_docs = list(dict.fromkeys(application.required_additional_docs + data.required_additional_docs))
        if application.status == "NEED_MORE_INFO":
            record(db, application, "UNDERWRITER", data.comment + ": " + ", ".join(data.required_additional_docs))
        else:
            transition(db, application, "NEED_MORE_INFO", "UNDERWRITER", data.comment + ": " + ", ".join(data.required_additional_docs))
    else:
        require_status(application, "MANUAL_UNDERWRITING")
        offer = data.offer.model_dump() if data.offer else make_offer(application.requested_amount, application.requested_term_months,
                                                                    application.product.interest_rate, application.product.product_type)
        p = application.product
        if offer["product_type"] != p.product_type or not p.min_amount <= offer["amount"] <= p.max_amount or not p.min_term_months <= offer["term_months"] <= p.max_term_months:
            raise HTTPException(422, "Условия оффера не соответствуют выбранному продукту")
        # Payment is always computed by the server, never trusted from input.
        offer = make_offer(offer["amount"], offer["term_months"], offer["interest_rate"], offer["product_type"])
        application.offers = [offer]
        application.selected_offer = None
        application.required_additional_docs = []
        transition(db, application, "OFFER_GENERATED", "UNDERWRITER", data.comment)
    db.flush()
